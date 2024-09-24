import json
from importlib import metadata
from pathlib import Path
from typing import Literal, Sequence

import aiosqlite
from ollama import Options
from packaging.version import parse

from oterm.config import envConfig
from oterm.store.chat import queries as chat_queries
from oterm.store.setup import queries as setup_queries
from oterm.store.upgrades import upgrades
from oterm.tools import Tool
from oterm.types import Author
from oterm.utils import int_to_semantic_version, semantic_version_to_int


class Store(object):
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
                await setup_queries.create_chat_table(connection)  # type: ignore
                await setup_queries.create_message_table(connection)  # type: ignore
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
            res = await setup_queries.get_user_version(connection)  # type: ignore
            return int_to_semantic_version(res[0][0])

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
        format: Literal["", "json"],
        parameters: Options,
        keep_alive: int,
        tools: list[Tool],
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res: list[tuple[int]] = await chat_queries.save_chat(  # type: ignore
                connection,
                id=id,
                name=name,
                model=model,
                system=system,
                format=format,
                parameters=json.dumps(parameters),
                keep_alive=keep_alive,
                tools=json.dumps(tools),
            )

            await connection.commit()
            return res[0][0]

    async def rename_chat(self, id: int, name: str) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.rename_chat(  # type: ignore
                connection,
                id=id,
                name=name,
            )
            await connection.commit()

    async def edit_chat(
        self,
        id: int,
        name: str,
        system: str | None,
        format: Literal["", "json"],
        parameters: Options,
        keep_alive: int,
        tools: list[Tool],
    ) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.edit_chat(  # type: ignore
                connection,
                id=id,
                name=name,
                system=system,
                format=format,
                parameters=json.dumps(parameters),
                keep_alive=keep_alive,
                tools=json.dumps(tools),
            )
            await connection.commit()

    async def get_chats(
        self,
    ) -> list[
        tuple[int, str, str, str | None, Literal["", "json"], Options, int, list[Tool]]
    ]:
        async with aiosqlite.connect(self.db_path) as connection:
            chats = await chat_queries.get_chats(connection)  # type: ignore
            chats = [
                (
                    id,
                    name,
                    model,
                    system,
                    format,
                    json.loads(parameters),
                    keep_alive,
                    json.loads(tools),
                )
                for id, name, model, system, format, parameters, keep_alive, tools in chats
            ]
            return chats

    async def get_chat(
        self, id
    ) -> (
        tuple[
            int, str, str, str | None, Literal["", "json"], Options, int, Sequence[Tool]
        ]
        | None
    ):
        async with aiosqlite.connect(self.db_path) as connection:
            chat = await chat_queries.get_chat(connection, id=id)  # type: ignore
            if chat:
                chat = chat[0]
                id, name, model, system, format, parameters, keep_alive, tools = chat
                return (
                    id,
                    name,
                    model,
                    system,
                    format,
                    json.loads(parameters),
                    keep_alive,
                    json.loads(tools),
                )

    async def delete_chat(self, id: int) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.delete_chat(connection, id=id)  # type: ignore
            await connection.commit()

    async def save_message(
        self, id: int | None, chat_id: int, author: str, text: str
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res = await chat_queries.save_message(  # type: ignore
                connection,
                id=id,
                chat_id=chat_id,
                author=author,
                text=text,
            )
            await connection.commit()
            return res[0][0]

    async def get_messages(self, chat_id: int) -> list[tuple[int, Author, str]]:

        async with aiosqlite.connect(self.db_path) as connection:
            messages = await chat_queries.get_messages(connection, chat_id=chat_id)  # type: ignore
            messages = [(id, Author(author), text) for id, author, text in messages]
            return messages
