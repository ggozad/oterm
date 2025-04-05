from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def images(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE message ADD COLUMN images TEXT DEFAULT "[]";
                """
            )
        except aiosqlite.OperationalError:
            pass

        await connection.commit()


async def orphan_messages(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                DELETE FROM message WHERE chat_id NOT IN (SELECT id FROM chat);
                """
            )
        except aiosqlite.OperationalError:
            pass

        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.7.0", [images, orphan_messages]),
]
