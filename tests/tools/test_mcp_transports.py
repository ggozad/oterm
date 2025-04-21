from fastmcp.client.transports import SSETransport, StdioTransport, WSTransport

from oterm.tools.mcp.client import MCPClient


def test_stdio_transport(mcp_server_config):
    """
    Test the MCP client with a StdioServerParameters.
    """

    client = MCPClient("test_stdio", mcp_server_config["stdio"])
    assert isinstance(client.transport, StdioTransport)


def test_sse_transport(mcp_server_config):
    client = MCPClient("test_sse", mcp_server_config["sse"])
    assert isinstance(client.transport, SSETransport)


def test_ws_transport(mcp_server_config):
    client = MCPClient("test_ws", mcp_server_config["ws"])
    assert isinstance(client.transport, WSTransport)
