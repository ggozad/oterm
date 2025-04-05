import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite

from oterm.ollamaclient import OllamaLLM, parse_ollama_parameters


async def parameters(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        try:
            await connection.executescript(
                """
                ALTER TABLE chat ADD COLUMN parameters TEXT DEFAULT "{}";
                """
            )
        except aiosqlite.OperationalError:
            pass

        # Update with default parameters
        chat_models = await connection.execute_fetchall("SELECT id, model FROM chat")
        for chat_id, model in chat_models:
            info = OllamaLLM.show(model)
            parameters = parse_ollama_parameters(info["parameters"])
            await connection.execute(
                "UPDATE chat SET parameters = ? WHERE id = ?",
                (json.dumps(parameters), chat_id),
            )
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.3.0", [parameters])
]
