import json
import sys
from importlib import metadata
from pathlib import Path
from typing import Literal

import aiosqlite
from oterm.app.chat import Author
from oterm.store.chat import queries as chat_queries
from oterm.store.setup import queries as setup_queries
from oterm.store.upgrades import upgrades
from packaging.version import parse


def semantic_version_to_int(version: str) -> int:
    """
    Convert a semantic version string to an integer.

    :param version: Semantic version string
    :type version: str
    :return: Integer representation of semantic version
    :rtype: int
    """
    major, minor, patch = version.split(".")
    major = int(major) << 16
    minor = int(minor) << 8
    patch = int(patch)
    return major + minor + patch


def int_to_semantic_version(version: int) -> str:
    """
    Convert an integer to a semantic version string.

    :param version: Integer representation of semantic version
    :type version: int
    :return: Semantic version string
    :rtype: str
    """
    major = version >> 16
    minor = (version >> 8) & 255
    patch = version & 255
    return f"{major}.{minor}.{patch}"


def get_data_dir() -> Path:
    """
    Get the user data directory for the current system platform.

    Linux: ~/.local/share/oterm
    macOS: ~/Library/Application Support/oterm
    Windows: C:/Users/<USER>/AppData/Roaming/oterm

    :return: User Data Path
    :rtype: str
    """
    home = Path.home()

    system_paths = {
        "win32": home / "AppData/Roaming/oterm",
        "linux": home / ".local/share/oterm",
        "darwin": home / "Library/Application Support/oterm",
    }

    data_path = system_paths[sys.platform]
    return data_path


class Store(object):
    db_path: Path

    @classmethod
    async def create(cls) -> "Store":
        self = Store()
        data_path = get_data_dir()
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

    async def save_chat(
        self,
        id: int | None,
        name: str,
        model: str,
        context: str,
        template: str | None,
        system: str | None,
        format: str | None,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res: list[tuple[int]] = await chat_queries.save_chat(  # type: ignore
                connection,
                id=id,
                name=name,
                model=model,
                context=context,
                template=template,
                system=system,
                format=format,
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

    async def get_chats(
        self,
    ) -> list[
        tuple[int, str, str, list[int], str | None, str | None, Literal["json"] | None]
    ]:
        async with aiosqlite.connect(self.db_path) as connection:
            chats = await chat_queries.get_chats(connection)  # type: ignore
            chats = [
                (id, name, model, json.loads(context), template, system, format)
                for id, name, model, context, template, system, format in chats
            ]
            return chats

    async def get_chat(
        self, id
    ) -> tuple[int, str, str, list[int], str | None, str | None] | None:
        async with aiosqlite.connect(self.db_path) as connection:
            chat = await chat_queries.get_chat(connection, id=id)  # type: ignore
            if chat:
                chat = chat[0]
                id, name, model, context, template, system = chat
                context = json.loads(context)
                return id, name, model, context, template, system

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
