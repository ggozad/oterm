from importlib import import_module
from typing import Awaitable, Callable, Sequence

from ollama._types import Tool

from oterm.config import appConfig
from oterm.types import ExternalToolDefinition, ToolDefinition


def load_tools(tool_defs: Sequence[ExternalToolDefinition]) -> Sequence[ToolDefinition]:
    tools = []
    for tool_def in tool_defs:
        tool_path = tool_def["tool"]

        try:
            module, tool = tool_path.split(":")
            module = import_module(module)
            tool = getattr(module, tool)
            if not isinstance(tool, Tool):
                raise Exception(f"Expected Tool, got {type(tool)}")
        except ModuleNotFoundError as e:
            raise Exception(f"Error loading tool {tool_path}: {str(e)}")

        callable_path = tool_def["callable"]
        try:
            module, function = callable_path.split(":")
            module = import_module(module)
            callable = getattr(module, function)
            if not isinstance(callable, (Callable, Awaitable)):
                raise Exception(f"Expected Callable, got {type(callable)}")
        except ModuleNotFoundError as e:
            raise Exception(f"Error loading callable {callable_path}: {str(e)}")
        tools.append({"tool": tool, "callable": callable})

    return tools


available: list[ToolDefinition] = []

external_tools = appConfig.get("tools")
if external_tools:
    available.extend(load_tools(external_tools))
