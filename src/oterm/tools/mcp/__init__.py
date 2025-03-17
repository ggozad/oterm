import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, McpError, StdioServerParameters
from mcp import Tool as MCPTool
from mcp.client.stdio import stdio_client
from mcp.types import Prompt
from textual import log

from oterm.config import appConfig
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.tools import MCPToolCallable, mcp_tool_to_ollama_tool
from oterm.types import ToolDefinition

mcp_clients: list[MCPClient] = []
mcp_prompts: list[Prompt] = []


async def setup_mcp_servers() -> tuple[list[ToolDefinition], list[Prompt]]:
    mcp_servers = appConfig.get("mcpServers")
    tool_defs: list[ToolDefinition] = []
    prompts: list[Prompt] = []
    if mcp_servers:
        for server, config in mcp_servers.items():
            # Patch the MCP server environment with the current environment
            # This works around https://github.com/modelcontextprotocol/python-sdk/issues/99
            from os import environ

            config = StdioServerParameters.model_validate(config)
            if config.env is not None:
                config.env.update(dict(environ))

            client = MCPClient(server, config)
            await client.initialize()
            if not client.session:
                continue
            mcp_clients.append(client)

            log.info(f"Initialized MCP server {server}")

            mcp_tools: list[MCPTool] = await client.get_available_tools()
            mcp_prompts = await client.get_available_prompts()
            prompts.extend(mcp_prompts)

            for mcp_tool in mcp_tools:
                tool = mcp_tool_to_ollama_tool(mcp_tool)
                mcpToolCallable = MCPToolCallable(mcp_tool.name, server, client)
                tool_defs.append({"tool": tool, "callable": mcpToolCallable.call})
                log.info(f"Loaded MCP tool {mcp_tool.name} from {server}")

    return tool_defs, prompts


async def teardown_mcp_servers():
    log.info("Tearing down MCP servers")
    # Important to tear down in reverse order
    mcp_clients.reverse()
    for client in mcp_clients:
        await client.cleanup()
