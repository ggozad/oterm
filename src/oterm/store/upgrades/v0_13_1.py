# Example upgrade script to remove type column from chat table
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def remove_type_column(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        await connection.executescript(
            """
            BEGIN TRANSACTION;

            CREATE TABLE chat_new (
                "id"        INTEGER,
                "name"      TEXT,
                "model"     TEXT NOT NULL,
                "system"    TEXT,
                "format"    TEXT,
                "parameters" TEXT DEFAULT "{}",
                "keep_alive" INTEGER DEFAULT 5,
                "tools"     TEXT DEFAULT "[]",
                PRIMARY KEY("id" AUTOINCREMENT)
            );

            INSERT INTO chat_new(id, name, model, system, format, parameters, keep_alive, tools)
            SELECT id, name, model, system, format, parameters, keep_alive, tools FROM chat;

            DROP TABLE chat;

            ALTER TABLE chat_new RENAME TO chat;

            COMMIT;
            """
        )


async def add_thinking_column(db_path):
    """Add thinking column to chat table."""
    async with aiosqlite.connect(db_path) as connection:
        await connection.execute(
            "ALTER TABLE chat ADD COLUMN thinking BOOLEAN DEFAULT 0"
        )
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.13.1", [remove_type_column, add_thinking_column])
]
