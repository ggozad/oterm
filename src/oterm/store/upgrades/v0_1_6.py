from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def add_template_system_to_chat(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        await connection.executescript(
            """
            ALTER TABLE chat ADD COLUMN template TEXT;
            ALTER TABLE chat ADD COLUMN system TEXT;
            """
        )


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.1.6", [add_template_system_to_chat])
]
