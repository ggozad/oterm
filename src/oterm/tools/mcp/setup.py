import contextlib
import os
import re
from typing import Any

from pydantic_ai.mcp import (
    MCPServer,
    MCPServerConfig,
    MCPServerSSE,
    MCPServerStdio,
    MCPServerStreamableHTTP,
)

from oterm.config import appConfig
from oterm.log import log
from oterm.tools.mcp.logging import Logger

# Subprocess env overrides that quiet common MCP server runtimes.
_STDIO_LOG_ENV = {
    "PYTHONUNBUFFERED": "0",
    "LOGLEVEL": "ERROR",
    "RUST_LOG": "error",
    "FASTMCP_LOG_LEVEL": "ERROR",
}

# Matches ${VAR} and ${VAR:-default} in string config values.
_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}")


class ToolMeta(dict):
    """Typed shape stored in `mcp_tool_meta`: {name, description}."""


mcp_servers: dict[str, MCPServer] = {}
mcp_tool_meta: dict[str, list[ToolMeta]] = {}
_exit_stack: contextlib.AsyncExitStack | None = None


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${VAR} / ${VAR:-default} in string values."""
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            has_default = match.group(2) is not None
            default = match.group(3) or ""
            if name in os.environ:
                return os.environ[name]
            if has_default:
                return default
            raise ValueError(f"Environment variable ${{{name}}} is not defined")

        return _ENV_VAR_PATTERN.sub(replace, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(v) for v in value]
    return value


def _build_servers(raw: dict[str, dict]) -> dict[str, MCPServer]:
    """Build MCP servers from oterm's config.

    Schema matches pydantic-ai's MCPServerConfig: each entry is either an
    stdio shape (`command` / `args` / `env`) or an HTTP shape (`url` /
    `headers`). URLs ending in `/sse` resolve to MCPServerSSE.
    """
    expanded = _expand_env_vars(raw)

    # Pre-validate: reject ws:// URLs explicitly so users get a clear error
    # instead of pydantic-ai trying to speak streamable-HTTP to a websocket.
    for name, entry in expanded.items():
        url = entry.get("url") if isinstance(entry, dict) else None
        if isinstance(url, str) and url.startswith(("ws://", "wss://")):
            raise ValueError(
                f"MCP server {name!r}: WebSocket transport is no longer supported. "
                "Use HTTP (http:// or https://) transport instead."
            )

    config = MCPServerConfig.model_validate({"mcpServers": expanded})

    servers: dict[str, MCPServer] = {}
    for name, server in config.mcp_servers.items():
        server.id = name
        server.log_handler = Logger()
        if isinstance(server, MCPServerStdio):
            server.env = {**_STDIO_LOG_ENV, **(server.env or {})}
        servers[name] = server
    return servers


async def setup_mcp_servers() -> dict[str, list[ToolMeta]]:
    """Build, enter, and probe each configured MCP server.

    Returns a registry of tool metadata per server name. The server instances
    themselves are stored in module-global `mcp_servers` and kept entered for
    the app lifetime via `_exit_stack`.
    """
    global _exit_stack
    configured = appConfig.get("mcpServers") or {}
    mcp_servers.clear()
    mcp_tool_meta.clear()
    _exit_stack = contextlib.AsyncExitStack()

    try:
        built = _build_servers(configured)
    except ValueError as e:
        log.error(f"MCP config rejected: {e}")
        return mcp_tool_meta
    except Exception as e:
        log.error(f"MCP config could not be parsed: {e}")
        return mcp_tool_meta

    for name, server in built.items():
        try:
            await _exit_stack.enter_async_context(server)
            tools = await server.list_tools()
        except Exception as e:
            log.error(f"MCP server {name!r} failed to initialize: {e}")
            continue
        mcp_servers[name] = server
        mcp_tool_meta[name] = [
            ToolMeta(name=t.name, description=t.description or "") for t in tools
        ]
        log.info(f"Loaded MCP server {name} with {len(tools)} tool(s)")

    return mcp_tool_meta


async def teardown_mcp_servers() -> None:
    global _exit_stack
    if _exit_stack is None:
        return
    log.info("Tearing down MCP servers")
    try:
        await _exit_stack.aclose()
    finally:
        _exit_stack = None
        mcp_servers.clear()
        mcp_tool_meta.clear()


# Re-export for tests + back-compat with anything that imported MCPServerSSE.
__all__ = [
    "MCPServer",
    "MCPServerSSE",
    "MCPServerStdio",
    "MCPServerStreamableHTTP",
    "ToolMeta",
    "mcp_servers",
    "mcp_tool_meta",
    "setup_mcp_servers",
    "teardown_mcp_servers",
]
