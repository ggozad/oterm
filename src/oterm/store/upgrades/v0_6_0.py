from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def tools(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat ADD COLUMN tools TEXT DEFAULT "[]";
                """
            )
        except aiosqlite.OperationalError:
            pass

        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.6.0", [tools])
]
