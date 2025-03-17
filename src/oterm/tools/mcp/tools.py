from mcp import Tool as MCPTool
from mcp.types import CallToolResult, TextContent
from textual import log

from oterm.types import Tool


class MCPToolCallable:
    def __init__(self, name, server_name, client):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs):
        log.info(f"Calling Tool {self.name} in {self.server_name} with {kwargs}")
        res: CallToolResult = await self.client.call_tool(self.name, kwargs)
        if res.isError:
            log.error(f"Error call mcp tool {self.name}.")
            raise Exception(f"Error call mcp tool {self.name}.")
        text_content = [m.text for m in res.content if type(m) is TextContent]
        return "\n".join(text_content)


def mcp_tool_to_ollama_tool(mcp_tool: MCPTool) -> Tool:
    """Convert an MCP tool to an Ollama tool"""

    return Tool(
        function=Tool.Function(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=Tool.Function.Parameters.model_validate(mcp_tool.inputSchema),
        ),
    )
