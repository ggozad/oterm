import json
import sys
from pathlib import Path

import aiosqlite
from oterm.app.chat import Author

from oterm.store.chat import queries as chat_queries
from oterm.store.setup import queries as setup_queries


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
        self.db_path = Path(data_path / "store.db")
        async with aiosqlite.connect(self.db_path) as connection:
            await setup_queries.create_chat_table(connection)  # type: ignore
            await setup_queries.create_message_table(connection)  # type: ignore

        return self

    async def save_chat(
        self, id: int | None, name: str, model: str, context: str
    ) -> int:
        async with aiosqlite.connect(self.db_path) as connection:
            res: list[tuple[int]] = await chat_queries.save_chat(  # type: ignore
                connection,
                id=id,
                name=name,
                model=model,
                context=context,
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

    async def get_chats(self) -> list[tuple[int, str, str, list[int]]]:
        async with aiosqlite.connect(self.db_path) as connection:
            chats = await chat_queries.get_chats(connection)  # type: ignore
            chats = [
                (id, name, model, json.loads(context))
                for id, name, model, context in chats
            ]
            return chats

    async def get_chat(self, id) -> tuple[int, str, str, list[int]] | None:
        async with aiosqlite.connect(self.db_path) as connection:
            chat = await chat_queries.get_chat(connection, id=id)  # type: ignore
            if chat:
                chat = chat[0]
                id, name, model, context = chat
                context = json.loads(context)
                return id, name, model, context

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
