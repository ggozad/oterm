from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def add_format_to_chat(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat ADD COLUMN format TEXT;
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.1.11", [add_format_to_chat]),
    ("0.1.13", [add_format_to_chat]),
]
