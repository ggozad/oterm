from typing import Awaitable, Callable, Sequence, TypedDict

from ollama._types import (
    Parameters,
    Property,
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolFunction,
)

from oterm.tools.date_time import DateTimeTool, date_time


class ToolDefinition(TypedDict):
    tool: Tool
    callable: Callable | Awaitable


available: Sequence[ToolDefinition] = [{"tool": DateTimeTool, "callable": date_time}]
