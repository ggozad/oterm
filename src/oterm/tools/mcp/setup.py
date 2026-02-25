from mcp import Tool as MCPTool

from oterm.config import appConfig
from oterm.log import log
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.prompts import MCPPromptCallable
from oterm.tools.mcp.tools import MCPToolCallable, mcp_tool_to_pydantic_tool
from oterm.types import PromptCall, ToolDef

mcp_clients: list[MCPClient] = []


async def setup_mcp_servers() -> tuple[
    dict[str, list[ToolDef]], dict[str, list[PromptCall]]
]:
    mcp_servers = appConfig.get("mcpServers")
    tool_defs: dict[str, list[ToolDef]] = {}
    prompt_calls: dict[str, list[PromptCall]] = {}

    if mcp_servers:
        for server, config in mcp_servers.items():
            client = MCPClient(server, config)
            await client.initialize()
            if not client.client:
                continue
            mcp_clients.append(client)

            log.info(f"Initialized MCP server {server}")

            mcp_tools: list[MCPTool] = await client.get_available_tools()
            mcp_prompts = await client.get_available_prompts()

            if mcp_tools:
                tool_defs[server] = []
            for mcp_tool in mcp_tools:
                mcp_callable = MCPToolCallable(mcp_tool.name, server, client)
                pydantic_tool = mcp_tool_to_pydantic_tool(mcp_tool, mcp_callable)
                tool_defs[server].append(
                    {
                        "name": mcp_tool.name,
                        "description": mcp_tool.description or "",
                        "tool": pydantic_tool,
                    }
                )
                log.info(f"Loaded MCP tool {mcp_tool.name} from {server}")

            if mcp_prompts:
                prompt_calls[server] = []

            for prompt in mcp_prompts:
                mcpPromptCallable = MCPPromptCallable(prompt.name, server, client)
                prompt_calls[server].append(
                    {"prompt": prompt, "callable": mcpPromptCallable.call}
                )
                log.info(f"Loaded MCP prompt {prompt.name} from {server}")

    return tool_defs, prompt_calls


async def teardown_mcp_servers():
    log.info("Tearing down MCP servers")
    # Important to tear down in reverse order
    mcp_clients.reverse()
    for client in mcp_clients:
        await client.teardown()
