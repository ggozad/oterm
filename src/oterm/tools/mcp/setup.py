import contextlib
import os
import re
from typing import Any

from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP

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


def _build_server(name: str, config: dict) -> MCPServer:
    """Translate an entry in appConfig['mcpServers'] to a pydantic-ai MCPServer."""
    config = _expand_env_vars(config)
    if "command" in config:
        env = {**_STDIO_LOG_ENV, **(config.get("env") or {})}
        return MCPServerStdio(
            command=config["command"],
            args=list(config.get("args", [])),
            env=env,
            cwd=config.get("cwd"),
            log_handler=Logger(),
            id=name,
        )
    if "url" in config:
        url = config["url"]
        if url.startswith(("ws://", "wss://")):
            raise ValueError(
                f"MCP server {name!r}: WebSocket transport is no longer supported. "
                "Use HTTP (http:// or https://) transport instead."
            )
        headers: dict[str, str] | None = None
        auth = config.get("auth") or {}
        if auth.get("type") == "bearer" and auth.get("token"):
            headers = {"Authorization": f"Bearer {auth['token']}"}
        return MCPServerStreamableHTTP(
            url=url,
            headers=headers,
            log_handler=Logger(),
            id=name,
        )
    raise ValueError(
        f"MCP server {name!r}: config must set either 'command' (stdio) "
        "or 'url' (streamable HTTP)."
    )


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

    for name, config in configured.items():
        try:
            server = _build_server(name, config)
        except ValueError as e:
            log.error(f"MCP server {name!r} skipped: {e}")
            continue
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
