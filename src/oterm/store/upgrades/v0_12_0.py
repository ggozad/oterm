from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def update_roles(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        await connection.executescript(
            """
            UPDATE message SET author = 'assistant' WHERE author = 'ollama';
            UPDATE message SET author = 'user' WHERE author = 'me';
            """
        )


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.12.0", [update_roles]),
]
