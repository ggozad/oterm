from collections.abc import Awaitable, Callable, Sequence
from importlib import import_module

from ollama import Tool

from oterm.log import log
from oterm.types import ExternalToolDefinition, ToolCall


def load_external_tools(
    external_tools: Sequence[ExternalToolDefinition],
) -> Sequence[ToolCall]:
    tools = []
    for tool_def in external_tools:
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
        log.info(f"Loaded tool {tool.function.name} from {tool_path}")  # type: ignore
        tools.append({"tool": tool, "callable": callable})

    return tools
