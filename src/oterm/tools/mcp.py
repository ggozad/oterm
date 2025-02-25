import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp import Tool as MCPTool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from textual import log

from oterm.config import appConfig
from oterm.types import Tool, ToolDefinition

mcp_clients = []


# adapted from mcp-python-sdk/examples/clients/simple-chatbot/mcp_simple_chatbot/main.py
class MCPClient:
    """Manages MCP server connections and tool execution."""

    def __init__(self, name: str, server_params: StdioServerParameters, errlog=None):
        self.name = name
        self.server_params = server_params
        self.errlog = errlog
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        """Initialize the server connection."""

        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(self.server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            await self.cleanup()
            raise e

    async def get_available_tools(self) -> list[MCPTool]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools_response = await self.session.list_tools()

        # Let's just ignore pagination for now
        return tools_response.tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool with retry mechanism.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If server is not initialized.
            Exception: If tool execution fails after all retries.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0
        while attempt < retries:
            try:
                result = await self.session.call_tool(tool_name, arguments)
                return result

            except Exception as e:
                attempt += 1
                log.warning(
                    f"Error executing tool: {e}. Attempt {attempt} of {retries}."
                )
                if attempt < retries:
                    log.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    log.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                log.error(f"Error during cleanup of MCP server {self.name}.")
                raise e


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


async def setup_mcp_servers():

    mcp_servers = appConfig.get("mcpServers")
    tool_defs: list[ToolDefinition] = []

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


def mcp_tool_to_ollama_tool(mcp_tool: MCPTool) -> Tool:
    """Convert an MCP tool to an Ollama tool"""

    return Tool(
        function=Tool.Function(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=Tool.Function.Parameters.model_validate(mcp_tool.inputSchema),
        ),
    )
