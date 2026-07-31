import json

import aiosqlite

from oterm.store.upgrades.v0_15_0 import (
    add_provider_remove_format_keep_alive,
    migrate_parameters,
    migrate_tools_to_names,
)
from oterm.store.upgrades.v0_18_0 import rename_providers
from oterm.store.upgrades.v0_22_0 import qualify_mcp_tool_names


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

    async def test_already_clean_parameters_skip_update(self, tmp_path):
        """Params that already match the keep list and have no num_predict skip the UPDATE."""
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, parameters) VALUES(?, ?, ?)",
                ("c", "m", json.dumps({"temperature": 0.5})),
            )
            await c.commit()

        await migrate_parameters(db)
        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT parameters FROM chat")
            params = json.loads(list(rows)[0][0])
            assert params == {"temperature": 0.5}


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


class TestQualifyMcpToolNames:
    @staticmethod
    def _servers(monkeypatch, meta, builtin=(), capabilities=()):
        import oterm.tools as tools_mod
        import oterm.tools.capabilities as capabilities_mod
        import oterm.tools.mcp.setup as mcp_setup_mod

        monkeypatch.setattr(tools_mod, "builtin_tools", [{"name": n} for n in builtin])
        monkeypatch.setattr(
            capabilities_mod, "capability_defs", [{"name": n} for n in capabilities]
        )
        monkeypatch.setattr(mcp_setup_mod, "mcp_tool_meta", meta)

    async def _chat_tools(self, db, tools):
        await _old_chat_schema(db)
        async with aiosqlite.connect(db) as c:
            await c.execute(
                "INSERT INTO chat(name, model, tools) VALUES(?, ?, ?)",
                ("c", "m", json.dumps(tools)),
            )
            await c.commit()

    @staticmethod
    async def _read_tools(db):
        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall("SELECT tools FROM chat")
            return json.loads(list(rows)[0][0])

    async def test_prefixes_bare_mcp_names_with_owning_server(
        self, tmp_path, monkeypatch
    ):
        db = tmp_path / "store.db"
        await self._chat_tools(db, ["shell", "list_pods"])
        self._servers(
            monkeypatch,
            {"k8s": [{"name": "list_pods", "description": ""}]},
            builtin=["shell"],
        )

        await qualify_mcp_tool_names(db)

        assert await self._read_tools(db) == ["shell", "k8s_list_pods"]

    async def test_ambiguous_name_expands_to_every_owning_server(
        self, tmp_path, monkeypatch
    ):
        """Pre-0.22 a bare name pulled in every server exporting it; keep that intent."""
        db = tmp_path / "store.db"
        await self._chat_tools(db, ["query_prometheus"])
        self._servers(
            monkeypatch,
            {
                "k8s": [{"name": "query_prometheus", "description": ""}],
                "grafana": [{"name": "query_prometheus", "description": ""}],
            },
        )

        await qualify_mcp_tool_names(db)

        assert await self._read_tools(db) == [
            "k8s_query_prometheus",
            "grafana_query_prometheus",
        ]

    async def test_builtin_and_capability_names_win_over_mcp(
        self, tmp_path, monkeypatch
    ):
        """An MCP server exporting `shell` must not steal the builtin selection."""
        db = tmp_path / "store.db"
        await self._chat_tools(db, ["shell", "memory"])
        self._servers(
            monkeypatch,
            {
                "sandbox": [
                    {"name": "shell", "description": ""},
                    {"name": "memory", "description": ""},
                ]
            },
            builtin=["shell"],
            capabilities=["memory"],
        )

        await qualify_mcp_tool_names(db)

        assert await self._read_tools(db) == ["shell", "memory"]

    async def test_unknown_names_are_left_untouched(self, tmp_path, monkeypatch):
        """A name no connected server exports is preserved rather than dropped."""
        db = tmp_path / "store.db"
        await self._chat_tools(db, ["ghost"])
        self._servers(monkeypatch, {"k8s": [{"name": "list_pods", "description": ""}]})

        await qualify_mcp_tool_names(db)

        assert await self._read_tools(db) == ["ghost"]

    async def test_no_connected_servers_is_noop(self, tmp_path, monkeypatch):
        db = tmp_path / "store.db"
        await self._chat_tools(db, ["list_pods"])
        self._servers(monkeypatch, {})

        await qualify_mcp_tool_names(db)

        assert await self._read_tools(db) == ["list_pods"]

    async def test_already_qualified_names_pass_through(self, tmp_path, monkeypatch):
        db = tmp_path / "store.db"
        await self._chat_tools(db, ["k8s_list_pods"])
        self._servers(monkeypatch, {"k8s": [{"name": "list_pods", "description": ""}]})

        await qualify_mcp_tool_names(db)

        assert await self._read_tools(db) == ["k8s_list_pods"]


class TestRenameProviders:
    async def test_renames_deprecated_provider_ids(self, tmp_path):
        db = tmp_path / "store.db"
        await _old_chat_schema(db)
        await add_provider_remove_format_keep_alive(db)
        async with aiosqlite.connect(db) as c:
            await c.executemany(
                "INSERT INTO chat(name, model, provider) VALUES(?, ?, ?)",
                [
                    ("a", "gpt-4o", "openai"),
                    ("b", "gemini-1.5", "google-gla"),
                    ("c", "gemini-1.5", "google-vertex"),
                    ("d", "llama3", "ollama"),
                ],
            )
            await c.commit()

        await rename_providers(db)

        async with aiosqlite.connect(db) as c:
            rows = await c.execute_fetchall(
                "SELECT name, provider FROM chat ORDER BY name"
            )
            assert list(rows) == [
                ("a", "openai-chat"),
                ("b", "google"),
                ("c", "google-cloud"),
                ("d", "ollama"),
            ]
