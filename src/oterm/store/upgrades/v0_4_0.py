from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def context(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat DROP COLUMN context;
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.4.0", [context])
]
