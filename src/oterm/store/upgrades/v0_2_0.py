from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def drop_template(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat DROP COLUMN template;
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.2.0", [drop_template])
]
