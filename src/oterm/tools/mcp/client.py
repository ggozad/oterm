import asyncio
from typing import Annotated, Any, Literal

from fastmcp.client import Client
from fastmcp.client.transports import (
    StdioTransport,
    StreamableHttpTransport,
)
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

isHTTPURL = Annotated[
    str, lambda v: v.startswith("http://") or v.startswith("https://")
]


class BearerTokenAuthentication(BaseModel):
    """Authentication parameters http-based transports."""

    type: Literal["bearer"]
    token: str


class StreamableHTTPServerParameters(BaseModel):
    """Parameters for the Streamable HTTP server."""

    url: isHTTPURL
    auth: BearerTokenAuthentication | None = None


class MCPClient:
    def __init__(
        self,
        name: str,
        config: StdioServerParameters | StreamableHTTPServerParameters,
    ):
        self.name = name

        self.client: Client | None = None
        try:
            cfg = StdioServerParameters.model_validate(config)
            # Suppress subprocess logging via environment variables
            env = cfg.env.copy() if cfg.env else {}
            # Set logging levels to suppress output from MCP server subprocess
            env["PYTHONUNBUFFERED"] = "0"  # Disable Python output buffering
            env["LOGLEVEL"] = "ERROR"  # Set log level to ERROR only
            env["RUST_LOG"] = "error"  # For Rust-based MCP servers
            env["FASTMCP_LOG_LEVEL"] = "ERROR"  # For FastMCP servers

            self.transport = StdioTransport(
                command=cfg.command,
                args=cfg.args,
                env=env,
                cwd=str(cfg.cwd) if cfg.cwd else None,
                keep_alive=False,
            )
            return
        except (ValidationError, ValueError):
            pass
        try:
            cfg = StreamableHTTPServerParameters.model_validate(config)
            self.transport = StreamableHttpTransport(
                url=cfg.url,
                auth=cfg.auth.token if cfg.auth and cfg.auth.type == "bearer" else None,
            )
            return
        except (ValidationError, ValueError):
            pass
        raise ValueError(f"Invalid transport type: {config}")

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
        if self.client and not self.client.is_connected():
            log.error(f"Failed to connect to MCP server {self.name}")
            self.client = None
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
            # Filter content to only include supported types

            filtered_content = []
            for item in result.content:
                if isinstance(item, TextContent | ImageContent | EmbeddedResource):
                    filtered_content.append(item)
            return filtered_content
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
