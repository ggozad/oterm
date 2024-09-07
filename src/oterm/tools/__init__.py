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
from oterm.tools.shell import ShellTool, shell_command


class ToolDefinition(TypedDict):
    tool: Tool
    callable: Callable | Awaitable


available: Sequence[ToolDefinition] = [
    {"tool": DateTimeTool, "callable": date_time},
    {"tool": ShellTool, "callable": shell_command},
]
