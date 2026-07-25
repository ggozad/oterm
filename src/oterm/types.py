from collections.abc import Callable
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.capabilities import AbstractCapability


class ToolDef(TypedDict):
    name: str
    description: str
    tool: PydanticTool


class CapabilityDef(TypedDict):
    name: str
    description: str
    factory: Callable[[], AbstractCapability[None]]


class ChatModel(BaseModel):
    """Chat model for storing chat metadata"""

    id: int | None = None
    name: str = ""
    model: str = ""
    system: str | None = None
    provider: str = "ollama"
    parameters: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    thinking: bool = False


class MessageModel(BaseModel):
    """Message model for storing chat messages"""

    id: int | None = None
    chat_id: int
    role: Literal["user", "assistant"]
    text: str
    images: list[str] = Field(default_factory=list)
