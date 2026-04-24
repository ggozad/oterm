from textual.app import App
from textual.widgets import Input

from oterm.app.chat_export import ChatExport, slugify
from oterm.types import ChatModel, MessageModel


class TestSlugify:
    def test_lowercases_and_hyphenates(self):
        assert slugify("Hello World!") == "hello-world"

    def test_strips_diacritics(self):
        assert slugify("café crème") == "cafe-creme"

    def test_collapses_multiple_whitespace(self):
        assert slugify("a   b   c") == "a-b-c"


class _Host(App):
    pass


async def test_escape_cancels(tmp_path):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        app.push_screen(
            ChatExport(chat_id=1, file_name=str(tmp_path / "chat.md")),
            lambda r: received.append(r),
        )
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]


async def test_submit_writes_file_and_dismisses(tmp_path, store):
    chat_id = await store.save_chat(ChatModel(name="c", model="m"))
    for role, text in (("user", "hi"), ("assistant", "hello")):
        await store.save_message(MessageModel(chat_id=chat_id, role=role, text=text))

    out = tmp_path / "chat.md"
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = ChatExport(chat_id=chat_id, file_name=str(out))
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        inp = screen.query_one("#chat-name-input", Input)
        inp.value = str(out)
        await pilot.press("enter")
        await pilot.pause()

    content = out.read_text()
    assert "*user*" in content
    assert "hi" in content
    assert "*assistant*" in content
    assert "hello" in content
    # Dismissed (with no explicit value — calls dismiss() at the end)
    assert received == [None]


async def test_empty_file_name_is_ignored(tmp_path, store):
    await store.save_chat(ChatModel(name="c", model="m"))
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = ChatExport(chat_id=1, file_name="")
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        inp = screen.query_one("#chat-name-input", Input)
        inp.value = ""
        await pilot.press("enter")
        await pilot.pause()
        assert received == []
