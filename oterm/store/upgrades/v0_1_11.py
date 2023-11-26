from pathlib import Path
from typing import Awaitable, Callable

import aiosqlite


async def add_format_to_chat(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        await connection.executescript(
            """
            ALTER TABLE chat ADD COLUMN format TEXT;
            """
        )


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.1.11", [add_format_to_chat])
]
