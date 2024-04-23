import json
from importlib import metadata
from pathlib import Path
from typing import Literal

import aiosqlite
from packaging.version import parse

from oterm.app.widgets.chat import Author
from oterm.config import envConfig
from oterm.store.chat import queries as chat_queries
from oterm.store.setup import queries as setup_queries
from oterm.store.upgrades import upgrades
from oterm.utils import int_to_semantic_version, semantic_version_to_int


class Store(object):
    db_path: Path

    @classmethod
    async def create(cls) -> "Store":
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

    @classmethod
    async def get_journal_mode(cls, db_path: str) -> str:
        async with aiosqlite.connect(db_path) as connection:
            res: list[tuple[int]] = await setup_queries.get_journal_mode(connection)
            return res[0][0]

    @classmethod
    async def set_journal_mode(cls, db_path: str, mode: str) -> bool:
        async with aiosqlite.connect(db_path) as connection:
            res = await connection.execute(
                f"PRAGMA journal_mode = {mode.upper()};"
            )
            status = await res.fetchall()
            if status[0][0].lower() == mode.lower():
                return True
            else:
                return False

    async def save_chat(
        self,
        id: int | None,
        name: str,
        model: str,
        context: str,
        system: str | None,
        format: Literal["", "json"],
        keep_alive: str | None,
        model_options: dict,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res: list[tuple[int]] = await chat_queries.save_chat(  # type: ignore
                connection,
                id=id,
                name=name,
                model=model,
                context=context,
                system=system,
                format=format,
                keep_alive=keep_alive,
                model_options=json.dumps(model_options),
            )

            await connection.commit()
            return res[0][0]

    async def save_context(self, id: int, context: str) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.save_context(  # type: ignore
                connection,
                id=id,
                context=context,
            )
            await connection.commit()

    async def rename_chat(self, id: int, name: str) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.rename_chat(  # type: ignore
                connection,
                id=id,
                name=name,
            )
            await connection.commit()

    async def edit_chat(
        self, id: int, name: str, system: str | None, format: Literal["", "json"], keep_alive: str | None, model_options: dict,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.edit_chat(  # type: ignore
                connection,
                id=id,
                name=name,
                system=system,
                format=format,
                keep_alive=keep_alive,
                model_options=json.dumps(model_options),
            )
            await connection.commit()

    async def get_chats(
        self,
    ) -> list[tuple[int, str, str, list[int], str | None, Literal["", "json"], str | None, str]]:
        async with aiosqlite.connect(self.db_path) as connection:
            chats = await chat_queries.get_chats(connection)  # type: ignore
            chats = [
                (id, name, model, json.loads(context), system, format, keep_alive, json.loads(model_options))
                for id, name, model, context, system, format, keep_alive, model_options in chats
            ]
            return chats

    async def get_chat(
        self, id
    ) -> tuple[int, str, str, list[int], str | None, Literal["", "json"], str | None, str] | None:
        async with aiosqlite.connect(self.db_path) as connection:
            chat = await chat_queries.get_chat(connection, id=id)  # type: ignore
            if chat:
                chat = chat[0]
                id, name, model, context, system, format, keep_alive, model_options = chat
                context = json.loads(context)
                model_options = json.loads(model_options)
                return id, name, model, context, system, format, keep_alive, model_options

    async def delete_chat(self, id: int) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.delete_chat(connection, id=id)  # type: ignore
            await connection.commit()

    async def save_message(self, chat_id: int, author: str, text: str) -> None:
        async with aiosqlite.connect(self.db_path) as connection:
            await chat_queries.save_message(  # type: ignore
                connection,
                chat_id=chat_id,
                author=author,
                text=text,
            )
            await connection.commit()

    async def get_messages(self, chat_id: int) -> list[tuple[Author, str]]:
        async with aiosqlite.connect(self.db_path) as connection:
            messages = await chat_queries.get_messages(connection, chat_id=chat_id)  # type: ignore
            messages = [(Author(author), text) for author, text in messages]
            return messages
