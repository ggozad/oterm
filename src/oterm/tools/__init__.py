from importlib import import_module
from typing import Awaitable, Callable, Sequence

from mcp import StdioServerParameters
from mcp import Tool as MCPTool
from mcp.types import CallToolResult, TextContent
from ollama._types import Tool

from oterm.config import appConfig
from oterm.tools.date_time import DateTimeTool, date_time
from oterm.tools.location import LocationTool, current_location
from oterm.tools.mcp import MCPClient, mcp_tool_to_ollama_tool
from oterm.tools.shell import ShellTool, shell_command
from oterm.tools.weather import WeatherTool, current_weather
from oterm.tools.web import WebTool, fetch_url
from oterm.types import ExternalToolDefinition, ToolDefinition

import logging
logger = logging.getLogger(__name__)

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

client_list = [ ]

class McpToolCallable:
    def __init__(self, name, server_name, client):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs):

        print(f"==== Call Tool {self.name} in {self.server_name} ====\n")

        res: CallToolResult = await self.client.call_tool(self.name, kwargs)
        if res.isError:
            raise Exception(f"Error call mcp tool {self.name}.")
        text_content = [
            m.text for m in res.content if type(m) is TextContent
        ]
        return "\n".join(text_content)


async def setup_mcp_servers():

    mcp_servers = appConfig.get("mcpServers")
    tool_defs: list[ToolDefinition] = []

    if mcp_servers:
        for server, config in mcp_servers.items():
            print(f"==== Starting {server} ====\n")
            client = MCPClient(
                StdioServerParameters.model_validate(config)
                )
            await client.initialize()
            print(f"=== passed initialize ===\n")

            # list of created clients
            client_list.append(client)

            mcp_tools: list[MCPTool] = await client.get_available_tools()

            for mcp_tool in mcp_tools:
                tool = mcp_tool_to_ollama_tool(mcp_tool)

                print(f"==== Defining Tool {mcp_tool.name} in {server} ====\n")
                print(f"==== {tool}")

                mcpToolCallable = McpToolCallable(mcp_tool.name, server, client)
                tool_defs.append({"tool": tool, "callable": mcpToolCallable.call})

    return tool_defs


async def teardown_mcp_servers():
    print(f"TEARDOWN LIST {client_list}\n")
    # Important to tear down in reverse order
    client_list.reverse()
    for client in client_list:
        print(f"TEARDOWN {client}\n")
        await client.cleanup()

        
