from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite

# pydantic-ai 1.100 renamed provider ids ahead of 2.0:
#   google-gla    → google
#   google-vertex → google-cloud
# and 2.0 moved bare `openai:` to the Responses API, so chats on the Chat
# Completions API are stored as `openai-chat`.
_PROVIDER_RENAMES = {
    "google-gla": "google",
    "google-vertex": "google-cloud",
    "openai": "openai-chat",
}


async def rename_providers(db_path: Path) -> None:
    async with aiosqlite.connect(db_path) as connection:
        for old, new in _PROVIDER_RENAMES.items():
            await connection.execute(
                "UPDATE chat SET provider = ? WHERE provider = ?", (new, old)
            )
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.18.0", [rename_providers]),
]
