import asyncio
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, McpError, StdioServerParameters
from mcp import Tool as MCPTool
from mcp.client.stdio import stdio_client
from mcp.types import Prompt
from textual import log


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
            await asyncio.wait_for(session.initialize(), timeout=5)
            self.session = session
        except Exception as e:
            await self.cleanup()
            log.error(f"Error initializing MCP server {self.name}: {e}")

    async def get_available_tools(self) -> list[MCPTool]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")
        try:
            tools_response = await self.session.list_tools()
        except McpError as e:
            log.error(f"Error listing tools for {self.name}: {e}")
            return []

        # Let's just ignore pagination for now
        return tools_response.tools

    async def get_available_prompts(self) -> list[Prompt]:
        """List available prompts from the server.

        Returns:
            A list of available prompts.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        try:
            prompts_response = await self.session.list_prompts()
        except McpError as e:
            log.error(f"Error listing prompts for {self.name}: {e}")
            return []

        for prompt in prompts_response.prompts:
            log.info(f"Loaded prompt {prompt.name} from {self.name}")

        return prompts_response.prompts

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
            except Exception:
                log.error(f"Error during cleanup of MCP server {self.name}.")
