from mcp import Tool as MCPTool
from mcp.types import TextContent
from pydantic_ai import Tool as PydanticTool

from oterm.tools.mcp.client import MCPClient


class MCPToolCallable:
    def __init__(self, name: str, server_name: str, client: MCPClient):
        self.name = name
        self.server_name = server_name
        self.client = client

    async def call(self, **kwargs) -> str:
        res = await self.client.call_tool(self.name, kwargs)
        text_content = [m.text for m in res if type(m) is TextContent]
        return "\n".join(text_content)


def mcp_tool_to_pydantic_tool(
    mcp_tool: MCPTool, callable: MCPToolCallable
) -> PydanticTool:
    """Convert an MCP tool to a Pydantic AI tool with proper schema."""
    return PydanticTool.from_schema(
        function=callable.call,
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        json_schema=mcp_tool.inputSchema,
        takes_ctx=False,
    )
