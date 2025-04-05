from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def update_format(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                UPDATE chat SET format = '' WHERE format is NULL;
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.2.4", [update_format])
]
