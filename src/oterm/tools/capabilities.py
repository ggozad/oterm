import os
from functools import cache
from importlib import import_module
from importlib.util import find_spec
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


@cache
def _speak() -> AbstractCapability[None]:
    # Shared across chats: the factory runs per chat and each Speaks owns worker
    # threads the factory contract gives no place to close.
    # onnxruntime reads this once, as it is imported.
    os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
    return import_module("pydantic_ai_tts").Speaks()


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


if find_spec("pydantic_ai_tts") is not None:
    capability_defs.append(
        {
            "name": "speak",
            "description": "Speak responses aloud as they stream.",
            "factory": _speak,
        }
    )
