import asyncio
from typing import Annotated, Any

from fastmcp.client import Client
from fastmcp.client.transports import SSETransport, StdioTransport, WSTransport
from mcp import McpError, StdioServerParameters
from mcp import Tool as MCPTool
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    Prompt,
    PromptMessage,
    TextContent,
)
from pydantic import BaseModel, ValidationError

from oterm.log import log
from oterm.tools.mcp.logging import Logger
from oterm.tools.mcp.sampling import sampling_handler

IsSSEURL = Annotated[str, lambda v: v.startswith("http://") or v.startswith("https://")]


class SSEServerParameters(BaseModel):
    """Parameters for the SSE server."""

    url: IsSSEURL


IsWSURL = Annotated[str, lambda v: v.startswith("ws://") or v.startswith("wss://")]


class WSServerParameters(BaseModel):
    """Parameters for the WS server."""

    url: IsWSURL


class MCPClient:
    def __init__(
        self,
        name: str,
        config: StdioServerParameters | SSEServerParameters | WSServerParameters,
    ):
        self.name = name

        self.client: Client | None = None
        try:
            cfg = StdioServerParameters.model_validate(config)
            self.transport = StdioTransport(
                command=cfg.command,
                args=cfg.args,
                env=cfg.env,
                cwd=str(cfg.cwd) if cfg.cwd else None,
            )
            return
        except ValidationError:
            pass
        try:
            cfg = SSEServerParameters.model_validate(config)
            self.transport = SSETransport(
                url=cfg.url,
            )
            return
        except (ValidationError, ValueError):
            pass
        try:
            cfg = WSServerParameters.model_validate(config)
            self.transport = WSTransport(
                url=cfg.url,
            )
        except ValidationError:
            raise ValueError("Invalid transport type")

    async def initialize(self) -> Client | None:
        """Initialize the server connection.

        Returns:
            The initialized client or None if initialization fails.
        """

        # We set up "done" as a future to signal when the client should shutdown.
        self.closed = asyncio.Event()
        self.done = asyncio.Event()
        # We wait for the client to be initialized before returning from initialize()
        client_initialized = asyncio.Event()

        async def task():
            assert self.transport is not None, "Transport is not initialized"
            try:
                async with Client(
                    self.transport,
                    log_handler=Logger(),
                    sampling_handler=sampling_handler,
                ) as client:
                    self.client = client
                    client_initialized.set()
                    await self.done.wait()
                self.closed.set()

            except Exception as e:
                log.error(f"Error initializing MCP server: {e}")
                client_initialized.set()

        self.task = asyncio.create_task(task())
        try:
            await asyncio.wait_for(client_initialized.wait(), timeout=5)
        except asyncio.TimeoutError:
            self.client = None
            log.error("Timeout while initializing MCP server", self.name)
        return self.client

    async def get_available_tools(self) -> list[MCPTool]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if self.client is None:
            raise RuntimeError("Client is not initialized")
        try:
            tools_response = await self.client.list_tools()
        except McpError:
            return []

        return tools_response

    async def get_available_prompts(self) -> list[Prompt]:
        """List available prompts from the server.

        Returns:
            A list of available prompts.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if self.client is None:
            raise RuntimeError(f"Server {self.name} not initialized")

        try:
            prompts = await self.client.list_prompts()
        except McpError:
            return []

        for prompt in prompts:
            log.info(f"Loaded prompt {prompt.name} from {self.name}")

        return prompts

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> list[TextContent | ImageContent | EmbeddedResource]:
        """Execute a tool

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If server is not initialized.
            Exception: If tool execution fails after all retries.
        """
        if not self.client:
            raise RuntimeError(f"Server {self.name} not initialized")

        try:
            result = await self.client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            log.error(f"Error executing tool: {e}.")
            return []

    async def call_prompt(
        self,
        prompt_name: str,
        arguments: dict[str, str],
    ) -> list[PromptMessage]:
        """Execute a prompt

        Args:
            prompt_name: Name of the prompt
            arguments: Prompt arguments.
        """

        if self.client is None:
            raise RuntimeError(f"Server {self.name} not initialized")
        try:
            result = await self.client.get_prompt(prompt_name, arguments)
            return result.messages
        except Exception as e:
            log.error(f"Error getting prompt: {e}.")
            return []

    async def teardown(self) -> None:
        if self.client is None:
            raise RuntimeError("Client is already closed")
        self.done.set()
        await self.closed.wait()
        self.client = None
        self.transport = None
