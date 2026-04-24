import pytest
from fastmcp.client.auth import BearerAuth
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

from oterm.tools.mcp.client import MCPClient


class TestTransportSelection:
    def test_stdio(self, mcp_server_config):
        client = MCPClient("stdio", mcp_server_config["stdio"])
        assert isinstance(client.transport, StdioTransport)

    def test_streamable_http(self, mcp_server_config):
        client = MCPClient("http", mcp_server_config["streamable_http"])
        assert isinstance(client.transport, StreamableHttpTransport)

    def test_bearer_auth(self, mcp_server_config):
        client = MCPClient("http-bearer", mcp_server_config["streamable_http_bearer"])
        assert isinstance(client.transport, StreamableHttpTransport)
        assert isinstance(client.transport.auth, BearerAuth)
        assert client.transport.auth.token.get_secret_value() == "test_token"

    def test_invalid_config_raises(self):
        with pytest.raises(ValueError, match="Invalid transport type"):
            MCPClient("broken", {"totally": "unknown"})  # ty: ignore[invalid-argument-type]


class TestStdioEnvironment:
    def test_logging_env_vars_set(self, mcp_server_config):
        from fastmcp.client.transports import StdioTransport

        client = MCPClient("stdio", mcp_server_config["stdio"])
        assert isinstance(client.transport, StdioTransport)
        env = client.transport.env or {}
        assert env.get("LOGLEVEL") == "ERROR"
        assert env.get("RUST_LOG") == "error"
        assert env.get("FASTMCP_LOG_LEVEL") == "ERROR"
        assert env.get("PYTHONUNBUFFERED") == "0"


class TestInitialize:
    async def test_stdio_initialize_and_teardown(self, mcp_client):
        assert mcp_client.client is not None
        assert mcp_client.client.is_connected()

    async def test_initialize_timeout_yields_none_client(
        self, mcp_server_config, monkeypatch
    ):
        from mcp import StdioServerParameters

        from oterm.tools.mcp import client as client_mod

        cfg = StdioServerParameters.model_validate({"command": "sleep", "args": ["30"]})
        client = MCPClient("hanging", cfg)
        monkeypatch.setattr(client_mod.asyncio, "wait_for", _raise_timeout)
        res = await client.initialize()
        assert res is None


async def _raise_timeout(aw, timeout):
    import asyncio

    raise asyncio.TimeoutError


class TestCallToolAndPrompt:
    async def test_call_tool_returns_text(self, mcp_client):
        from mcp.types import TextContent

        result = await mcp_client.call_tool("oracle", {"query": "hi"})
        texts = [c.text for c in result if isinstance(c, TextContent)]
        assert any("oterm" in t.lower() for t in texts)

    async def test_call_tool_on_unknown_tool_returns_empty(self, mcp_client):
        import oterm.log

        before = len(oterm.log.log_lines)
        result = await mcp_client.call_tool("not_a_real_tool", {})
        assert result == []
        messages = [msg for _, msg in oterm.log.log_lines[before:]]
        assert any("Error executing tool" in m for m in messages)

    async def test_call_prompt(self, mcp_client):
        from mcp.types import TextContent

        messages = await mcp_client.call_prompt("oracle_prompt", {"question": "What?"})
        assert len(messages) == 1
        content = messages[0].content
        assert isinstance(content, TextContent)
        assert content.text == "Oracle: What?"

    async def test_call_prompt_unknown_returns_empty(self, mcp_client):
        import oterm.log

        before = len(oterm.log.log_lines)
        result = await mcp_client.call_prompt("ghost", {})
        assert result == []
        messages = [msg for _, msg in oterm.log.log_lines[before:]]
        assert any("Error getting prompt" in m for m in messages)

    async def test_teardown_on_uninitialised_client_raises(self, mcp_server_config):
        client = MCPClient("stdio", mcp_server_config["stdio"])
        with pytest.raises(RuntimeError, match="Client is already closed"):
            await client.teardown()


class TestNotInitialisedErrors:
    async def test_get_tools_before_init_raises(self, mcp_server_config):
        client = MCPClient("stdio", mcp_server_config["stdio"])
        with pytest.raises(RuntimeError, match="Client is not initialized"):
            await client.get_available_tools()

    async def test_get_prompts_before_init_raises(self, mcp_server_config):
        client = MCPClient("stdio", mcp_server_config["stdio"])
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.get_available_prompts()

    async def test_call_tool_before_init_raises(self, mcp_server_config):
        client = MCPClient("stdio", mcp_server_config["stdio"])
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.call_tool("x", {})

    async def test_call_prompt_before_init_raises(self, mcp_server_config):
        client = MCPClient("stdio", mcp_server_config["stdio"])
        with pytest.raises(RuntimeError, match="not initialized"):
            await client.call_prompt("x", {})
