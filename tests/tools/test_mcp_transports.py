from fastmcp.client.transports import (
    StdioTransport,
    StreamableHttpTransport,
)

from oterm.tools.mcp.client import MCPClient


def test_stdio_transport(mcp_server_config):
    """
    Test the MCP client with a StdioServerParameters.
    """

    client = MCPClient("test_stdio", mcp_server_config["stdio"])
    assert isinstance(client.transport, StdioTransport)


def test_streamable_http(mcp_server_config):
    client = MCPClient("test_streamable_http", mcp_server_config["streamable_http"])
    assert isinstance(client.transport, StreamableHttpTransport)
