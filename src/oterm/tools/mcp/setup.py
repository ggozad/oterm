import contextlib

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from oterm.config import appConfig
from oterm.log import log
from oterm.tools.mcp.logging import Logger
from oterm.utils import expand_env_vars

# Subprocess env overrides that quiet common MCP server runtimes.
_STDIO_LOG_ENV = {
    "PYTHONUNBUFFERED": "0",
    "LOGLEVEL": "ERROR",
    "RUST_LOG": "error",
    "FASTMCP_LOG_LEVEL": "ERROR",
}


class ToolMeta(dict):
    """Typed shape stored in `mcp_tool_meta`: {name, description}."""


mcp_servers: dict[str, MCPToolset] = {}
mcp_tool_meta: dict[str, list[ToolMeta]] = {}
_exit_stack: contextlib.AsyncExitStack | None = None


def _build_toolset(name: str, entry: dict) -> MCPToolset:
    """Build a single MCPToolset from an oterm `mcpServers` config entry.

    Accepts either an HTTP shape (`url` / `headers`) or a stdio shape
    (`command` / `args` / `env` / `cwd`). Rejects WebSocket URLs explicitly
    so users get a clear error instead of a transport-layer failure.
    """
    url = entry.get("url")
    if isinstance(url, str):
        if url.startswith(("ws://", "wss://")):
            raise ValueError(
                f"MCP server {name!r}: WebSocket transport is no longer supported. "
                "Use HTTP (http:// or https://) transport instead."
            )
        return MCPToolset(
            url,
            id=name,
            headers=entry.get("headers"),
            log_handler=Logger(),
        )
    transport = StdioTransport(
        command=entry["command"],
        args=list(entry.get("args") or []),
        env={**_STDIO_LOG_ENV, **(entry.get("env") or {})},
        cwd=entry.get("cwd"),
    )
    return MCPToolset(transport, id=name, log_handler=Logger())


def _build_toolsets(raw: dict[str, dict]) -> dict[str, MCPToolset]:
    """Build MCPToolsets from oterm's `mcpServers` config block.

    Schema matches the Claude Desktop / pydantic-ai convention: each entry is
    either an stdio shape (`command` / `args` / `env` / `cwd`) or an HTTP
    shape (`url` / `headers`). URLs ending in `/sse` resolve to an SSE
    transport automatically; other HTTP URLs use Streamable HTTP.
    """
    expanded = expand_env_vars(raw)
    return {name: _build_toolset(name, entry) for name, entry in expanded.items()}


async def setup_mcp_servers() -> dict[str, list[ToolMeta]]:
    """Build, enter, and probe each configured MCP server.

    Returns a registry of tool metadata per server name. The toolset instances
    themselves are stored in module-global `mcp_servers` and kept entered for
    the app lifetime via `_exit_stack`.
    """
    global _exit_stack
    configured = appConfig.get("mcpServers") or {}
    mcp_servers.clear()
    mcp_tool_meta.clear()
    _exit_stack = contextlib.AsyncExitStack()

    try:
        built = _build_toolsets(configured)
    except ValueError as e:
        log.error(f"MCP config rejected: {e}")
        return mcp_tool_meta
    except Exception as e:
        log.error(f"MCP config could not be parsed: {e}")
        return mcp_tool_meta

    for name, toolset in built.items():
        try:
            await _exit_stack.enter_async_context(toolset)
            tools = await toolset.list_tools()
        except Exception as e:
            log.error(f"MCP server {name!r} failed to initialize: {e}")
            continue
        mcp_servers[name] = toolset
        mcp_tool_meta[name] = [
            ToolMeta(name=t.name, description=t.description or "") for t in tools
        ]
        log.info(f"Loaded MCP server {name} with {len(tools)} tool(s)")

    return mcp_tool_meta


async def teardown_mcp_servers() -> None:
    global _exit_stack
    if _exit_stack is None:  # pragma: no cover
        return
    log.info("Tearing down MCP servers")
    try:
        await _exit_stack.aclose()
    finally:
        _exit_stack = None
        mcp_servers.clear()
        mcp_tool_meta.clear()


__all__ = [
    "ToolMeta",
    "mcp_servers",
    "mcp_tool_meta",
    "setup_mcp_servers",
    "teardown_mcp_servers",
]
