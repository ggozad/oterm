from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def keep_alive(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat ADD COLUMN keep_alive INTEGER DEFAULT 5;
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.2.8", [keep_alive])
]
