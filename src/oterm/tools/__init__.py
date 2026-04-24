from collections.abc import Callable
from importlib.metadata import entry_points

from pydantic_ai import Tool as PydanticTool

from oterm.types import ToolDef

# Populated from the `oterm.tools` entry points at app startup.
builtin_tools: list[ToolDef] = []


def make_tool_def(func: Callable) -> ToolDef:
    pydantic_tool = PydanticTool(func, takes_ctx=False)
    return {
        "name": pydantic_tool.name,
        "description": pydantic_tool.description or "",
        "tool": pydantic_tool,
    }


def discover_tools() -> list[ToolDef]:
    """Discover tools registered via the ``oterm.tools`` entry-point group."""
    from oterm.log import log

    tools: list[ToolDef] = []
    for ep in entry_points(group="oterm.tools"):
        try:
            func = ep.load()
            if not callable(func):
                log.error(f"Entry point {ep.name} is not callable, skipping")
                continue
            tools.append(make_tool_def(func))
            log.info(f"Discovered tool {ep.name} from {ep.value}")
        except Exception as e:
            log.error(f"Failed to load tool entry point {ep.name}: {e}")
    return tools
