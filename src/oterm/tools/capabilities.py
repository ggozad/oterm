from pathlib import Path

from pydantic_ai.capabilities import AbstractCapability, WebFetch, WebSearch
from pydantic_ai_harness import FileSystem
from pydantic_ai_harness.memory import Memory, SqliteMemoryStore

from oterm.types import CapabilityDef


def _web_search() -> AbstractCapability[None]:
    return WebSearch(local="duckduckgo")


def _web_fetch() -> AbstractCapability[None]:
    return WebFetch(local=True)


def _memory() -> AbstractCapability[None]:
    from oterm.config import envConfig

    return Memory(
        store=SqliteMemoryStore(database=envConfig.OTERM_DATA_DIR / "memory.db")
    )


def _filesystem() -> AbstractCapability[None]:
    return FileSystem(root_dir=Path.cwd())


capability_defs: list[CapabilityDef] = [
    {
        "name": "web_search",
        "description": "Search the web. Uses the provider's native web search when available, DuckDuckGo otherwise.",
        "factory": _web_search,
    },
    {
        "name": "web_fetch",
        "description": "Fetch the contents of a URL. Uses the provider's native fetching when available.",
        "factory": _web_fetch,
    },
    {
        "name": "memory",
        "description": "Persistent memory notebook, shared across all chats.",
        "factory": _memory,
    },
    {
        "name": "filesystem",
        "description": "Read, write and search files under the directory oterm was started from.",
        "factory": _filesystem,
    },
]
