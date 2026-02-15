from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def add_template_system_to_chat(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        res = await connection.execute("PRAGMA table_info(chat);")
        columns = {row[1] for row in await res.fetchall()}

        if "template" not in columns:
            await connection.execute("ALTER TABLE chat ADD COLUMN template TEXT;")
        if "system" not in columns:
            await connection.execute("ALTER TABLE chat ADD COLUMN system TEXT;")
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.1.6", [add_template_system_to_chat])
]
