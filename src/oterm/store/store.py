import json
from importlib import metadata
from pathlib import Path

import aiosqlite
from ollama import Options
from packaging.version import parse

from oterm.config import envConfig
from oterm.store.upgrades import upgrades
from oterm.types import Author, Tool
from oterm.utils import int_to_semantic_version, semantic_version_to_int


class Store:
    db_path: Path

    _store: "Store | None" = None

    @classmethod
    async def get_store(cls) -> "Store":
        if cls._store is not None:
            return cls._store
        self = Store()
        data_path = envConfig.OTERM_DATA_DIR
        data_path.mkdir(parents=True, exist_ok=True)
        self.db_path = data_path / "store.db"

        if not self.db_path.exists():
            # Create tables and set user_version
            async with aiosqlite.connect(self.db_path) as connection:
                await connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS "chat" (
                        "id"		INTEGER,
                        "name"		TEXT,
                        "model"		TEXT NOT NULL,
                        "system"	TEXT,
                        "format"	TEXT,
                        "parameters"	TEXT DEFAULT "{}",
                        "keep_alive" INTEGER DEFAULT 5,
                        "tools" 	TEXT DEFAULT "[]",
                        "type"      TEXT DEFAULT "chat",
                        PRIMARY KEY("id" AUTOINCREMENT)
                    );

                    CREATE TABLE IF NOT EXISTS "message" (
                        "id"		INTEGER,
                        "chat_id"	INTEGER NOT NULL,
                        "author"	TEXT NOT NULL,
                        "text"		TEXT NOT NULL,
                        "images"    TEXT DEFAULT "[]",
                        PRIMARY KEY("id" AUTOINCREMENT)
                        FOREIGN KEY("chat_id") REFERENCES "chat"("id") ON DELETE CASCADE
                    );
                """
                )
                await self.set_user_version(metadata.version("oterm"))
        else:
            # Upgrade database
            current_version: str = metadata.version("oterm")
            db_version = await self.get_user_version()
            for version, steps in upgrades:
                if parse(current_version) >= parse(version) and parse(version) > parse(
                    db_version
                ):
                    for step in steps:
                        await step(self.db_path)
            await self.set_user_version(current_version)
        cls._store = self
        return self

    async def get_user_version(self) -> str:
        async with aiosqlite.connect(self.db_path) as connection:
            res = await connection.execute("PRAGMA user_version;")
            res = await res.fetchone()
            return int_to_semantic_version(res[0] if res else 0)

    async def set_user_version(self, version: str) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await connection.execute(
                f"PRAGMA user_version = {semantic_version_to_int(version)};"
            )

    async def save_chat(
        self,
        id: int | None,
        name: str,
        model: str,
        system: str | None,
        format: str,
        parameters: Options,
        keep_alive: int,
        tools: list[Tool],
        type: str = "chat",
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res = await connection.execute_insert(
                """
                INSERT OR REPLACE
                INTO chat(id, name, model, system, format, parameters, keep_alive, tools, type)
                VALUES(:id, :name, :model, :system, :format, :parameters, :keep_alive, :tools, :type) RETURNING id;""",
                {
                    "id": id,
                    "name": name,
                    "model": model,
                    "system": system,
                    "format": format,
                    "parameters": json.dumps(parameters),
                    "keep_alive": keep_alive,
                    "tools": json.dumps(tools),
                    "type": type,
                },
            )
            await connection.commit()

        return res[0] if res else 0

    async def rename_chat(self, id: int, name: str) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await connection.execute(
                "UPDATE chat SET name = :name WHERE id = :id;", {"id": id, "name": name}
            )
            await connection.commit()

    async def edit_chat(
        self,
        id: int,
        name: str,
        system: str | None,
        format: str,
        parameters: Options,
        keep_alive: int,
        tools: list[Tool],
    ) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await connection.execute(
                """
                UPDATE chat
                SET name = :name,
                    system = :system,
                    format = :format,
                    parameters = :parameters,
                    keep_alive = :keep_alive,
                    tools = :tools
                WHERE id = :id;
                """,
                {
                    "id": id,
                    "name": name,
                    "system": system,
                    "format": format,
                    "parameters": json.dumps(parameters),
                    "keep_alive": keep_alive,
                    "tools": json.dumps(tools),
                },
            )
            await connection.commit()

    async def get_chats(
        self, type="chat"
    ) -> list[tuple[int, str, str, str | None, str, Options, int, list[Tool]]]:
        async with aiosqlite.connect(self.db_path) as connection:
            chats = await connection.execute_fetchall(
                """
                SELECT id, name, model, system, format, parameters, keep_alive, tools
                FROM chat WHERE type = :type;
                """,
                {"type": type},
            )
            return [
                (
                    id,
                    name,
                    model,
                    system,
                    format,
                    Options(**json.loads(parameters)),
                    keep_alive,
                    [Tool(**t) for t in json.loads(tools)],
                )
                for id, name, model, system, format, parameters, keep_alive, tools in chats
            ]

    async def get_chat(
        self, id: int
    ) -> tuple[int, str, str, str | None, str, Options, int, list[Tool], str] | None:
        async with aiosqlite.connect(self.db_path) as connection:
            chat = await connection.execute_fetchall(
                """
                SELECT id, name, model, system, format, parameters, keep_alive, tools, type
                FROM chat
                WHERE id = :id;
                """,
                {"id": id},
            )
            chat = next(iter(chat), None)
            if chat:
                id, name, model, system, format, parameters, keep_alive, tools, type = (
                    chat
                )
                return (
                    id,
                    name,
                    model,
                    system,
                    format,
                    Options(**json.loads(parameters)),
                    keep_alive,
                    [Tool(**t) for t in json.loads(tools)],
                    type,
                )

    async def delete_chat(self, id: int) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await connection.execute("PRAGMA foreign_keys = on;")
            await connection.execute("DELETE FROM chat WHERE id = :id;", {"id": id})
            await connection.commit()

    async def save_message(
        self,
        id: int | None,
        chat_id: int,
        author: str,
        text: str,
        images: list[str] = [],
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res = await connection.execute_insert(
                """
                INSERT OR REPLACE
                INTO message(id, chat_id, author, text, images)
                VALUES(:id, :chat_id, :author, :text, :images) RETURNING id;
                """,
                {
                    "id": id,
                    "chat_id": chat_id,
                    "author": author,
                    "text": text,
                    "images": json.dumps(images),
                },
            )
            await connection.commit()
            return res[0] if res else 0

    async def get_messages(
        self, chat_id: int
    ) -> list[tuple[int, Author, str, list[str]]]:
        async with aiosqlite.connect(self.db_path) as connection:
            messages = await connection.execute_fetchall(
                """
                SELECT id, author, text, images
                FROM message
                WHERE chat_id = :chat_id;
                """,
                {"chat_id": chat_id},
            )
            messages = [
                (id, Author(author), text, json.loads(images))
                for id, author, text, images in messages
            ]
            return messages

    async def clear_chat(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await connection.execute(
                "DELETE FROM message WHERE chat_id = :chat_id;", {"chat_id": chat_id}
            )
            await connection.commit()
