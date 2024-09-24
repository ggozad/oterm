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
from oterm.tools.location import LocationTool, current_location
from oterm.tools.shell import ShellTool, shell_command
from oterm.tools.weather import WeatherTool, current_weather


class ToolDefinition(TypedDict):
    tool: Tool
    callable: Callable | Awaitable


available: Sequence[ToolDefinition] = [
    {"tool": DateTimeTool, "callable": date_time},
    {"tool": ShellTool, "callable": shell_command},
    {"tool": LocationTool, "callable": current_location},
    {"tool": WeatherTool, "callable": current_weather},
]
