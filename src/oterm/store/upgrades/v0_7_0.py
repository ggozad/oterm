from pathlib import Path
from typing import Awaitable, Callable

import aiosqlite


async def tools(db_path: Path) -> None:
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


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.7.0", [tools])
]
