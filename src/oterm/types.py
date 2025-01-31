from enum import Enum
from typing import Awaitable, Callable, TypedDict

from ollama._types import Image, Tool  # noqa


class Author(Enum):
    USER = "me"
    OLLAMA = "ollama"


class ParsedResponse(TypedDict):
    thought: str
    response: str
    formatted_output: str


class ToolDefinition(TypedDict):
    tool: Tool
    callable: Callable | Awaitable


class ExternalToolDefinition(TypedDict):
    tool: str
    callable: str
