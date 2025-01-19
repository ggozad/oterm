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


async def setup_mcp_servers():
    mcp_servers = appConfig.get("mcpServers")
    tool_defs: list[ToolDefinition] = []
    if mcp_servers:
        for server, config in mcp_servers.items():
            async with MCPClient(
                StdioServerParameters.model_validate(config)
            ) as client:
                mcp_tools: list[MCPTool] = await client.get_available_tools()

                for mcp_tool in mcp_tools:
                    tool = mcp_tool_to_ollama_tool(mcp_tool)

                    async def callable(name=mcp_tool.name, **kwargs):
                        async with MCPClient(
                            StdioServerParameters.model_validate(config)
                        ) as cl:
                            res: CallToolResult = await cl.call_tool(name, kwargs)
                            if res.isError:
                                raise Exception(f"Error call mcp tool {name}.")
                            text_content = [
                                m.text for m in res.content if type(m) is TextContent
                            ]
                            return "\n".join(text_content)

                    tool_defs.append({"tool": tool, "callable": callable})

    return tool_defs
