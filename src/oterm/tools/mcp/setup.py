from mcp import StdioServerParameters
from mcp import Tool as MCPTool

from oterm.config import appConfig
from oterm.log import log
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.prompts import MCPPromptCallable
from oterm.tools.mcp.tools import MCPToolCallable, mcp_tool_to_ollama_tool
from oterm.types import PromptCall, ToolCall

mcp_clients: list[MCPClient] = []


async def setup_mcp_servers() -> tuple[list[ToolCall], list[PromptCall]]:
    mcp_servers = appConfig.get("mcpServers")
    tool_calls: list[ToolCall] = []
    prompt_calls: list[PromptCall] = []

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

            for mcp_tool in mcp_tools:
                tool = mcp_tool_to_ollama_tool(mcp_tool)
                mcpToolCallable = MCPToolCallable(mcp_tool.name, server, client)
                tool_calls.append({"tool": tool, "callable": mcpToolCallable.call})
                log.info(f"Loaded MCP tool {mcp_tool.name} from {server}")

            for prompt in mcp_prompts:
                mcpPromptCallable = MCPPromptCallable(prompt.name, server, client)
                prompt_calls.append(
                    {"prompt": prompt, "callable": mcpPromptCallable.call}
                )
                log.info(f"Loaded MCP prompt {prompt.name} from {server}")

    return tool_calls, prompt_calls


async def teardown_mcp_servers():
    log.info("Tearing down MCP servers")
    # Important to tear down in reverse order
    mcp_clients.reverse()
    for client in mcp_clients:
        await client.cleanup()
