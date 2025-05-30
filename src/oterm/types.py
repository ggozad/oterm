from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict

from mcp.types import Prompt
from ollama import Options, Tool
from pydantic import BaseModel, Field


class ParsedResponse(BaseModel):
    thought: str
    response: str
    formatted_output: str


class ToolCall(TypedDict):
    tool: Tool
    callable: Callable | Awaitable


class PromptCall(TypedDict):
    prompt: Prompt
    callable: Callable | Awaitable


class ExternalToolDefinition(TypedDict):
    tool: str
    callable: str


class OtermOllamaOptions(Options):
    # Patch stop to allow for a single string.
    # This is an issue with the gemma model which has a single stop parameter.
    # Remove when fixed upstream and close #187
    # Using 'any' to avoid type conflict with parent class
    stop: Any = None  # type: ignore

    class Config:
        extra = "forbid"


class ChatModel(BaseModel):
    """Chat model for storing chat metadata"""

    id: int | None = None
    name: str = ""
    model: str = ""
    system: str | None = None
    format: str = ""
    parameters: OtermOllamaOptions = Field(default_factory=OtermOllamaOptions)
    keep_alive: int = 5
    tools: list[Tool] = Field(default_factory=list)
    thinking: bool = False


class MessageModel(BaseModel):
    """Message model for storing chat messages"""

    id: int | None = None
    chat_id: int
    role: Literal["user", "assistant", "system", "tool"]
    text: str
    images: list[str] = Field(default_factory=list)
