from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def chat_type(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat ADD COLUMN type TEXT DEFAULT "chat";
                """
            )
        except aiosqlite.OperationalError:
            pass

        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.9.0", [chat_type]),
]
