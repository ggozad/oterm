import aiosqlite

from oterm.store.store import Store
from oterm.types import ChatModel, MessageModel


async def test_fresh_db_is_created(tmp_data_dir):
    store = await Store.get_store()
    assert store.db_path.exists()
    assert store.db_path == tmp_data_dir / "store.db"


async def test_store_is_singleton_per_process(tmp_data_dir):
    a = await Store.get_store()
    b = await Store.get_store()
    assert a is b


async def test_singleton_reset_picks_up_new_data_dir(
    tmp_data_dir, tmp_path, monkeypatch
):
    first = await Store.get_store()
    assert first.db_path.parent == tmp_data_dir

    import oterm.config

    new_dir = tmp_path / "other"
    new_dir.mkdir()
    monkeypatch.setattr(oterm.config.envConfig, "OTERM_DATA_DIR", new_dir)
    monkeypatch.setattr(Store, "_store", None)

    second = await Store.get_store()
    assert second.db_path.parent == new_dir
    assert second is not first


async def test_save_and_get_chats(store: Store):
    chat = ChatModel(
        name="c1",
        model="llama3",
        system="be terse",
        provider="ollama",
        parameters={"temperature": 0.4},
        tools=["date_time"],
        thinking=True,
    )
    chat_id = await store.save_chat(chat)
    chat.id = chat_id

    chats = await store.get_chats()
    assert len(chats) == 1
    stored = chats[0]
    assert stored.id == chat_id
    assert stored.name == "c1"
    assert stored.parameters == {"temperature": 0.4}
    assert stored.tools == ["date_time"]
    assert stored.thinking is True


async def test_get_chat_by_id(store: Store):
    chat = ChatModel(name="solo", model="m")
    chat_id = await store.save_chat(chat)

    found = await store.get_chat(chat_id)
    assert found is not None
    assert found.id == chat_id
    assert found.name == "solo"


async def test_get_chat_missing_returns_none(store: Store):
    assert await store.get_chat(9999) is None


async def test_rename_chat(store: Store):
    chat = ChatModel(name="old", model="m")
    chat_id = await store.save_chat(chat)
    await store.rename_chat(chat_id, "new")
    found = await store.get_chat(chat_id)
    assert found is not None and found.name == "new"


async def test_edit_chat_updates_mutable_fields(store: Store):
    chat = ChatModel(name="c", model="m", parameters={"temperature": 0.1})
    chat_id = await store.save_chat(chat)

    chat.id = chat_id
    chat.name = "renamed"
    chat.system = "be curt"
    chat.parameters = {"temperature": 0.9}
    chat.tools = ["shell"]
    chat.thinking = True
    await store.edit_chat(chat)

    found = await store.get_chat(chat_id)
    assert found is not None
    assert found.name == "renamed"
    assert found.system == "be curt"
    assert found.parameters == {"temperature": 0.9}
    assert found.tools == ["shell"]
    assert found.thinking is True


async def test_delete_chat_cascades_to_messages(store: Store):
    chat_id = await store.save_chat(ChatModel(name="c", model="m"))
    await store.save_message(MessageModel(chat_id=chat_id, role="user", text="hello"))

    await store.delete_chat(chat_id)
    assert await store.get_chat(chat_id) is None
    messages = await store.get_messages(chat_id)
    assert messages == []


async def test_save_and_get_messages(store: Store):
    chat_id = await store.save_chat(ChatModel(name="c", model="m"))

    msg = MessageModel(chat_id=chat_id, role="user", text="hi", images=["b64"])
    msg_id = await store.save_message(msg)
    assert msg_id > 0

    messages = await store.get_messages(chat_id)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].text == "hi"
    assert messages[0].images == ["b64"]


async def test_clear_chat_removes_messages(store: Store):
    chat_id = await store.save_chat(ChatModel(name="c", model="m"))
    await store.save_message(MessageModel(chat_id=chat_id, role="user", text="a"))
    await store.save_message(MessageModel(chat_id=chat_id, role="assistant", text="b"))

    await store.clear_chat(chat_id)
    assert await store.get_messages(chat_id) == []


async def test_user_version_round_trip(store: Store):
    await store.set_user_version("1.2.3")
    assert await store.get_user_version() == "1.2.3"


async def test_existing_db_triggers_upgrades(tmp_data_dir, monkeypatch):
    """Simulate an old DB and ensure upgrade steps run on init."""
    import oterm.store.store as store_module

    db_path = tmp_data_dir / "store.db"
    async with aiosqlite.connect(db_path) as connection:
        await connection.executescript(
            """
            CREATE TABLE chat (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                model TEXT NOT NULL,
                system TEXT,
                format TEXT,
                keep_alive TEXT,
                parameters TEXT DEFAULT '{}',
                tools TEXT DEFAULT '[]',
                thinking BOOLEAN DEFAULT 0
            );
            CREATE TABLE message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                author TEXT NOT NULL,
                text TEXT NOT NULL,
                images TEXT DEFAULT '[]'
            );
            """
        )
        await connection.commit()

    calls: list[str] = []

    async def fake_step(path):
        calls.append(str(path))

    # Swap in a single fake step so we can assert the dispatcher ran it
    # without depending on the real upgrade SQL matching our seeded schema.
    monkeypatch.setattr(store_module, "upgrades", [("99.0.0", [fake_step])])
    monkeypatch.setattr(Store, "_store", None)

    import importlib.metadata as meta

    monkeypatch.setattr(meta, "version", lambda name: "99.0.0")

    store = await Store.get_store()
    assert calls == [str(db_path)]
    assert await store.get_user_version() == "99.0.0"


async def test_existing_db_skips_upgrades_if_current(tmp_data_dir, monkeypatch):
    """If db version >= current, no upgrade steps run."""
    import importlib.metadata as meta

    import oterm.store.store as store_module

    db_path = tmp_data_dir / "store.db"
    async with aiosqlite.connect(db_path) as connection:
        await connection.execute("PRAGMA user_version = 16777215")  # 255.255.255
        await connection.commit()

    called = False

    async def should_not_run(path):
        nonlocal called
        called = True

    monkeypatch.setattr(store_module, "upgrades", [("0.15.0", [should_not_run])])
    monkeypatch.setattr(Store, "_store", None)
    monkeypatch.setattr(meta, "version", lambda name: "255.255.255")

    await Store.get_store()
    assert called is False
