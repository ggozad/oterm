from importlib import import_module
from typing import Awaitable, Callable, Sequence

from mcp import StdioServerParameters
from mcp import Tool as MCPTool
from mcp.types import CallToolResult, TextContent
from ollama._types import Tool
from textual import log

from oterm.config import appConfig
from oterm.tools.mcp import MCPClient, mcp_tool_to_ollama_tool
from oterm.types import ExternalToolDefinition, ToolDefinition


def load_tools(tool_defs: Sequence[ExternalToolDefinition]) -> Sequence[ToolDefinition]:
    tools = []
    for tool_def in tool_defs:
        tool_path = tool_def["tool"]

        try:
            module, tool = tool_path.split(":")
            module = import_module(module)
            tool = getattr(module, tool)
            if not isinstance(tool, Tool):
                raise Exception(f"Expected Tool, got {type(tool)}")
        except ModuleNotFoundError as e:
            raise Exception(f"Error loading tool {tool_path}: {str(e)}")

        callable_path = tool_def["callable"]
        try:
            module, function = callable_path.split(":")
            module = import_module(module)
            callable = getattr(module, function)
            if not isinstance(callable, (Callable, Awaitable)):
                raise Exception(f"Expected Callable, got {type(callable)}")
        except ModuleNotFoundError as e:
            raise Exception(f"Error loading callable {callable_path}: {str(e)}")
        tools.append({"tool": tool, "callable": callable})

    return tools


available: list[ToolDefinition] = []

external_tools = appConfig.get("tools")
if external_tools:
    available.extend(load_tools(external_tools))

mcp_clients = []


class MCPToolCallable:
    def __init__(self, name, server_name, client):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs):

        log.info(f"Calling Tool {self.name} in {self.server_name} with {kwargs}")
        print(self.client.call_tool)
        res: CallToolResult = await self.client.call_tool(self.name, kwargs)
        if res.isError:
            print(res)
            print(dir(res))
            print(res.content)
            raise Exception(f"Error call mcp tool {self.name}.")
        text_content = [m.text for m in res.content if type(m) is TextContent]
        return "\n".join(text_content)


async def setup_mcp_servers():

    mcp_servers = appConfig.get("mcpServers")
    tool_defs: list[ToolDefinition] = []

    log.info("Setting up MCP servers")
    if mcp_servers:
        for server, config in mcp_servers.items():
            client = MCPClient(server, StdioServerParameters.model_validate(config))
            await client.initialize()
            mcp_clients.append(client)
            log.info(f"Initialized MCP server {server}")

            mcp_tools: list[MCPTool] = await client.get_available_tools()

            for mcp_tool in mcp_tools:
                tool = mcp_tool_to_ollama_tool(mcp_tool)
                mcpToolCallable = MCPToolCallable(mcp_tool.name, server, client)
                tool_defs.append({"tool": tool, "callable": mcpToolCallable.call})
                log.info(f"Loaded MCP tool {mcp_tool.name} from {server}")

    return tool_defs


async def teardown_mcp_servers():

    log.info("Tearing down MCP servers")
    # Important to tear down in reverse order
    mcp_clients.reverse()
    for client in mcp_clients:
        await client.cleanup()
