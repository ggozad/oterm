from collections.abc import Callable
from importlib.metadata import entry_points

from pydantic_ai import Tool as PydanticTool

from oterm.types import ToolDef

# Populated from the `oterm.tools` entry points at app startup.
builtin_tools: list[ToolDef] = []


def qualified_tool_name(server: str, tool: str) -> str:
    """Identity of an MCP tool, matching the name `PrefixedToolset` exposes."""
    return f"{server}_{tool}"


def known_tool_names() -> set[str]:
    """Names of everything currently selectable (builtin + capabilities + connected MCP)."""
    from oterm.tools.capabilities import capability_defs
    from oterm.tools.mcp.setup import mcp_tool_meta

    names = {t["name"] for t in builtin_tools}
    names.update(c["name"] for c in capability_defs)
    for server, metas in mcp_tool_meta.items():
        names.update(qualified_tool_name(server, m["name"]) for m in metas)
    return names


def make_tool_def(func: Callable) -> ToolDef:
    pydantic_tool = PydanticTool(func, takes_ctx=False)
    return {
        "name": pydantic_tool.name,
        "description": pydantic_tool.description or "",
        "tool": pydantic_tool,
    }


async def load_tools() -> None:
    """Populate `builtin_tools` and connect the configured MCP servers."""
    from oterm.tools.mcp.setup import setup_mcp_servers

    builtin_tools.clear()
    builtin_tools.extend(discover_tools())
    await setup_mcp_servers()


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
