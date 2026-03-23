from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def add_provider_column(db_path: Path) -> None:
    """Add provider column to chat table for multi-provider support."""
    async with aiosqlite.connect(db_path) as connection:
        await connection.execute(
            "ALTER TABLE chat ADD COLUMN provider TEXT DEFAULT 'ollama'"
        )
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.14.8", [add_provider_column])
]
