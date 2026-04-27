import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def add_provider_remove_format_keep_alive(db_path: Path) -> None:
    """Migrate chat table: add provider column, remove format and keep_alive columns."""
    async with aiosqlite.connect(db_path) as connection:
        await connection.executescript(
            """
            BEGIN TRANSACTION;

            CREATE TABLE chat_new (
                "id"        INTEGER,
                "name"      TEXT,
                "model"     TEXT NOT NULL,
                "system"    TEXT,
                "provider"  TEXT DEFAULT "ollama",
                "parameters" TEXT DEFAULT "{}",
                "tools"     TEXT DEFAULT "[]",
                "thinking"  BOOLEAN DEFAULT 0,
                PRIMARY KEY("id" AUTOINCREMENT)
            );

            INSERT INTO chat_new(id, name, model, system, provider, parameters, tools, thinking)
            SELECT id, name, model, system, "ollama", parameters, tools, thinking FROM chat;

            DROP TABLE chat;

            ALTER TABLE chat_new RENAME TO chat;

            COMMIT;
            """
        )


async def migrate_parameters(db_path: Path) -> None:
    """Clean up parameters: keep only temperature, top_p, max_tokens.

    Maps num_predict → max_tokens if max_tokens not already present.
    """
    async with aiosqlite.connect(db_path) as connection:
        chats = await connection.execute_fetchall("SELECT id, parameters FROM chat")
        for chat_id, params_json in chats:
            params = json.loads(params_json)
            if not params:
                continue
            cleaned: dict[str, object] = {}
            if "temperature" in params:
                cleaned["temperature"] = params["temperature"]
            if "top_p" in params:
                cleaned["top_p"] = params["top_p"]
            if "max_tokens" in params:
                cleaned["max_tokens"] = params["max_tokens"]
            elif "num_predict" in params:
                cleaned["max_tokens"] = params["num_predict"]
            if cleaned != params:
                await connection.execute(
                    "UPDATE chat SET parameters = ? WHERE id = ?",
                    (json.dumps(cleaned), chat_id),
                )
        await connection.commit()


async def migrate_tools_to_names(db_path: Path) -> None:
    """Migrate tools from JSON objects (ollama.Tool format) to name strings."""
    async with aiosqlite.connect(db_path) as connection:
        chats = await connection.execute_fetchall("SELECT id, tools FROM chat")
        for chat_id, tools_json in chats:
            tools = json.loads(tools_json)
            if tools and isinstance(tools[0], dict):
                # Old format: list of ollama.Tool objects with function.name
                names = []
                for tool in tools:
                    if (
                        "function" in tool and "name" in tool["function"]
                    ):  # pragma: no branch
                        names.append(tool["function"]["name"])
                await connection.execute(
                    "UPDATE chat SET tools = ? WHERE id = ?",
                    (json.dumps(names), chat_id),
                )
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    (
        "0.15.0",
        [
            add_provider_remove_format_keep_alive,
            migrate_tools_to_names,
            migrate_parameters,
        ],
    )
]
