from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field
from pydantic_ai import Tool as PydanticTool


class ToolDef(TypedDict):
    name: str
    description: str
    tool: PydanticTool


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
    role: Literal["user", "assistant", "system", "tool"]
    text: str
    images: list[str] = Field(default_factory=list)
