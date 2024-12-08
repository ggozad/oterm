from enum import Enum
from typing import Awaitable, Callable, TypedDict

from ollama._types import Image, Tool  # noqa


class Author(Enum):
    USER = "me"
    OLLAMA = "ollama"


class ToolDefinition(TypedDict):
    tool: Tool
    callable: Callable | Awaitable
