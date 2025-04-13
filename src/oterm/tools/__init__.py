from collections.abc import Awaitable, Callable, Sequence
from importlib import import_module

from ollama import Tool

from oterm.config import appConfig
from oterm.log import log
from oterm.types import ExternalToolDefinition, ToolCall


def load_tools(tool_defs: Sequence[ExternalToolDefinition]) -> Sequence[ToolCall]:
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
            log.error(f"Error loading tool {tool_path}: {e}")
            continue

        callable_path = tool_def["callable"]
        try:
            module, function = callable_path.split(":")
            module = import_module(module)
            callable = getattr(module, function)
            if not isinstance(callable, Callable | Awaitable):
                raise Exception(f"Expected Callable, got {type(callable)}")
        except ModuleNotFoundError as e:
            log.error(f"Error loading callable {callable_path}: {e}")
            continue
        log.info(f"Loaded tool {tool.function.name} from {tool_path}")
        tools.append({"tool": tool, "callable": callable})

    return tools


avail_tool_defs: list[ToolCall] = []

external_tools = appConfig.get("tools")
if external_tools:
    avail_tool_defs.extend(load_tools(external_tools))
