from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def add_id_to_messages(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                CREATE TABLE message_temp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    author TEXT NOT NULL,
                    text TEXT NOT NULL
                );
                INSERT INTO message_temp (chat_id, author, text) SELECT chat_id, author, text FROM message;
                DROP TABLE message;
                ALTER TABLE message_temp RENAME TO message;
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.5.1", [add_id_to_messages])
]
