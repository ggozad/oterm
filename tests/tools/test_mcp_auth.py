from fastmcp.client.auth import BearerAuth
from fastmcp.client.transports import StreamableHttpTransport

from oterm.tools.mcp.client import (
    MCPClient,
)


def test_mcp_bearer_auth_transport_creation(mcp_server_config):
    """Test that bearer authentication creates the correct transport type."""
    client = MCPClient("bearer_auth", mcp_server_config["streamable_http_bearer"])
    assert isinstance(client.transport, StreamableHttpTransport)
    assert hasattr(client.transport, "auth")
    assert isinstance(client.transport.auth, BearerAuth)
    assert client.transport.auth.token.get_secret_value() == "test_token"
