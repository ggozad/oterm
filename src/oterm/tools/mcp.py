from mcp import ClientSession, ListToolsResult, StdioServerParameters
from mcp import Tool as MCPTool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from oterm.types import Tool


class MCPClient:
    """Client for interacting with MCP servers"""

    def __init__(self, server_params: StdioServerParameters, errlog=None):
        self.server_params = server_params
        self.session = None
        self._client = None
        self.errlog = errlog

    async def __aenter__(self):
        """Async context manager entry"""
        if not self._client:
            await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
#        if self.session:
#            await self.session.__aexit__(exc_type, exc_val, exc_tb)
#        if self._client:
#            await self._client.__aexit__(exc_type, exc_val, exc_tb)

    async def connect(self):
        self._client = stdio_client(self.server_params, errlog=self.errlog)
        self.read, self.write = await self._client.__aenter__()
        session = ClientSession(self.read, self.write)
        self.session = await session.__aenter__()
        await self.session.initialize()

    async def get_available_tools(self) -> list[MCPTool]:
        """List available tools"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        tools: ListToolsResult = await self.session.list_tools()
        # Let's just ignore pagination for now
        return tools.tools

    async def call_tool(self, tool_name: str, arguments: dict) -> CallToolResult:
        """Call a tool with given arguments"""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        result = await self.session.call_tool(tool_name, arguments=arguments)
        return result


def mcp_tool_to_ollama_tool(mcp_tool: MCPTool) -> Tool:
    """Convert an MCP tool to an Ollama tool"""

    return Tool(
        function=Tool.Function(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=Tool.Function.Parameters.model_validate(mcp_tool.inputSchema),
        ),
    )
