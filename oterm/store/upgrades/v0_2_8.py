from pathlib import Path
from typing import Awaitable, Callable

import aiosqlite


async def add_keep_alive_to_chat(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat ADD COLUMN keep_alive TEXT;
                ALTER TABLE chat ADD COLUMN model_options TEXT NOT NULL DEFAULT '{}';
                """
            )
        except aiosqlite.OperationalError:
            pass


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.2.8", [add_keep_alive_to_chat])
]
