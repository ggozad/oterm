from mcp import ClientSession, ListToolsResult, StdioServerParameters
from mcp import Tool as MCPTool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from contextlib import AsyncExitStack
from typing import Any
import asyncio

from oterm.types import Tool

import logging
logger = logging.getLogger(__name__)

# adapted from mcp-python-sdk/examples/clients/simple-chatbot/mcp_simple_chatbot/main.py
class MCPClient:
    """Manages MCP server connections and tool execution."""

    def __init__(self, server_params: StdioServerParameters, errlog=None):
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
                stdio_client(self.server_params, errlog=self.errlog)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

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
                logging.info(f"Executing {tool_name}...")
                result = await self.session.call_tool(tool_name, arguments)

                return result

            except Exception as e:
                attempt += 1
                logging.warning(
                    f"Error executing tool: {e}. Attempt {attempt} of {retries}."
                )
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")


def mcp_tool_to_ollama_tool(mcp_tool: MCPTool) -> Tool:
    """Convert an MCP tool to an Ollama tool"""

    return Tool(
        function=Tool.Function(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=Tool.Function.Parameters.model_validate(mcp_tool.inputSchema),
        ),
    )
