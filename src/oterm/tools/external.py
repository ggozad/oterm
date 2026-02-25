from collections.abc import Sequence
from importlib import import_module

from pydantic_ai import Tool as PydanticTool

from oterm.log import log
from oterm.types import ExternalToolDefinition, ToolDef


def load_external_tools(
    external_tools: Sequence[ExternalToolDefinition],
) -> Sequence[ToolDef]:
    tools: list[ToolDef] = []
    for tool_def in external_tools:
        callable_path = tool_def["callable"]
        try:
            module_path, function_name = callable_path.split(":")
            module = import_module(module_path)
            func = getattr(module, function_name)
            if not callable(func):
                raise Exception(f"Expected Callable, got {type(func)}")
        except ModuleNotFoundError as e:
            log.error(f"Error loading callable {callable_path}: {e}")
            continue

        pydantic_tool = PydanticTool(func, takes_ctx=False)
        name = pydantic_tool.name
        description = pydantic_tool.description or ""
        log.info(f"Loaded external tool {name} from {callable_path}")
        tools.append({"name": name, "description": description, "tool": pydantic_tool})

    return tools
