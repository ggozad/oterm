import importlib
import pkgutil
from typing import Awaitable, Callable, Sequence, TypedDict

from attr import has
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

try:
    import otermtools  # type: ignore  # noqa: I001

    # otermtools is a namespace, let's discover all the modules and tools in it.
    modules = pkgutil.iter_modules(otermtools.__path__)
    for module in modules:
        module_name = f"otermtools.{module.name}"
        module = importlib.import_module(module_name)
        if hasattr(module, "tools"):
            for tool in module.tools:
                available.append(tool)
except ImportError:
    pass
