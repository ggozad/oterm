import json

import aiosqlite

from oterm.store.upgrades.v0_15_0 import (
    add_provider_remove_format_keep_alive,
    migrate_parameters,
    migrate_tools_to_names,
)


async def _old_chat_schema(db_path):
    """Pre-0.15 schema: has format + keep_alive, no provider."""
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
            """
        )
        await connection.commit()


class TestAddProviderRemoveFormatKeepAlive:
    async def test_adds_provider_and_drops_old_cols(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, format, keep_alive) VALUES(?, ?, ?, ?)",
                ("c1", "llama3", "json", "5m"),
            )
            await c.commit()

        await add_provider_remove_format_keep_alive(db)

        async with aiosqlite.connect(db) as c:
            cols_cursor = await c.execute("PRAGMA table_info(chat)")
            cols = {row[1] for row in await cols_cursor.fetchall()}
            assert "provider" in cols
            assert "format" not in cols
            assert "keep_alive" not in cols

            rows = await c.execute_fetchall("SELECT name, model, provider FROM chat")
            assert list(rows) == [("c1", "llama3", "ollama")]


class TestMigrateParameters:
    async def test_keeps_known_keys_and_drops_unknown(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, parameters) VALUES(?, ?, ?)",
                (
                    "c",
                    "m",
                    json.dumps(
                        {
                            "temperature": 0.4,
                            "top_p": 0.9,
                            "max_tokens": 64,
                            "mirostat": 1,
                        }
                    ),
                ),
            )
            await c.commit()

        await migrate_parameters(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT parameters FROM chat")
            params = json.loads(list(rows)[0][0])
            assert params == {"temperature": 0.4, "top_p": 0.9, "max_tokens": 64}

    async def test_maps_num_predict_to_max_tokens(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, parameters) VALUES(?, ?, ?)",
                ("c", "m", json.dumps({"num_predict": 128, "temperature": 0.1})),
            )
            await c.commit()

        await migrate_parameters(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT parameters FROM chat")
            params = json.loads(list(rows)[0][0])
            assert params == {"temperature": 0.1, "max_tokens": 128}

    async def test_explicit_max_tokens_wins_over_num_predict(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, parameters) VALUES(?, ?, ?)",
                ("c", "m", json.dumps({"num_predict": 128, "max_tokens": 256})),
            )
            await c.commit()

        await migrate_parameters(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT parameters FROM chat")
            params = json.loads(list(rows)[0][0])
            assert params == {"max_tokens": 256}

    async def test_empty_parameters_is_noop(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, parameters) VALUES(?, ?, ?)",
                ("c", "m", "{}"),
            )
            await c.commit()

        await migrate_parameters(db)
        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT parameters FROM chat")
            assert list(rows)[0][0] == "{}"


class TestMigrateToolsToNames:
    async def test_converts_old_tool_objects_to_names(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, tools) VALUES(?, ?, ?)",
                (
                    "c",
                    "m",
                    json.dumps(
                        [
                            {"function": {"name": "date_time"}},
                            {"function": {"name": "shell"}},
                        ]
                    ),
                ),
            )
            await c.commit()

        await migrate_tools_to_names(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT tools FROM chat")
            tools = json.loads(list(rows)[0][0])
            assert tools == ["date_time", "shell"]

    async def test_new_format_passes_through(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, tools) VALUES(?, ?, ?)",
                ("c", "m", json.dumps(["date_time"])),
            )
            await c.commit()

        await migrate_tools_to_names(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT tools FROM chat")
            assert json.loads(list(rows)[0][0]) == ["date_time"]

    async def test_empty_tools_is_noop(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, tools) VALUES(?, ?, ?)",
                ("c", "m", "[]"),
            )
            await c.commit()

        await migrate_tools_to_names(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT tools FROM chat")
            assert list(rows)[0][0] == "[]"
