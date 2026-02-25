import itertools
from collections.abc import Callable

from pydantic_ai import Tool as PydanticTool

from oterm.types import ToolDef

available_tool_defs: dict[str, list[ToolDef]] = {}


def available_tools() -> list[ToolDef]:
    return list(itertools.chain.from_iterable(available_tool_defs.values()))


def make_tool_def(func: Callable) -> ToolDef:
    pydantic_tool = PydanticTool(func, takes_ctx=False)
    return {
        "name": pydantic_tool.name,
        "description": pydantic_tool.description or "",
        "tool": pydantic_tool,
    }
