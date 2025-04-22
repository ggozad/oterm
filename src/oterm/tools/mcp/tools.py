from mcp import Tool as MCPTool
from mcp.types import TextContent

from oterm.tools.mcp.client import MCPClient
from oterm.types import Tool


class MCPToolCallable:
    def __init__(self, name: str, server_name: str, client: MCPClient):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs) -> str:
        res = await self.client.call_tool(self.name, kwargs)
        text_content = [m.text for m in res if type(m) is TextContent]
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
