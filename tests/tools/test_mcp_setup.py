import pytest
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

from oterm.tools.mcp.setup import (
    _build_server,
    mcp_servers,
    setup_mcp_servers,
    teardown_mcp_servers,
)


class TestBuildServer:
    def test_stdio_config(self):
        server = _build_server(
            "stdio",
            {"command": "mcp", "args": ["run", "x"], "env": {"FOO": "bar"}},
        )
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["LOGLEVEL"] == "ERROR"
        assert env["FOO"] == "bar"

    def test_stdio_does_not_inherit_parent_env(self, monkeypatch):
        """Secure default: parent env (PATH, secrets, etc.) is not leaked."""
        monkeypatch.setenv("SECRET_TOKEN", "leak-me")
        server = _build_server("stdio", {"command": "mcp"})
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert "SECRET_TOKEN" not in env
        assert "PATH" not in env

    def test_stdio_user_env_overrides_logging_overrides(self):
        server = _build_server(
            "stdio",
            {"command": "mcp", "args": [], "env": {"LOGLEVEL": "DEBUG"}},
        )
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["LOGLEVEL"] == "DEBUG"

    def test_env_var_substitution_in_env_values(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "shh")
        server = _build_server(
            "stdio",
            {"command": "mcp", "env": {"GITHUB_TOKEN": "${MY_TOKEN}"}},
        )
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["GITHUB_TOKEN"] == "shh"

    def test_env_var_substitution_in_command_and_args(self, monkeypatch):
        monkeypatch.setenv("MCP_BIN", "/opt/bin/mcp")
        server = _build_server(
            "stdio",
            {"command": "${MCP_BIN}", "args": ["--config", "${MCP_BIN}.conf"]},
        )
        assert isinstance(server, MCPServerStdio)
        assert server.command == "/opt/bin/mcp"
        assert list(server.args) == ["--config", "/opt/bin/mcp.conf"]

    def test_env_var_substitution_with_default(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        server = _build_server(
            "stdio",
            {"command": "mcp", "env": {"DEFAULTED": "${MISSING_VAR:-fallback}"}},
        )
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["DEFAULTED"] == "fallback"

    def test_env_var_substitution_missing_raises(self, monkeypatch):
        monkeypatch.delenv("UNDEFINED_VAR", raising=False)
        with pytest.raises(ValueError, match="UNDEFINED_VAR"):
            _build_server(
                "stdio",
                {"command": "mcp", "env": {"X": "${UNDEFINED_VAR}"}},
            )

    def test_env_var_substitution_in_bearer_token(self, monkeypatch):
        monkeypatch.setenv("BEARER", "s3cret")
        server = _build_server(
            "http",
            {
                "url": "http://x/mcp",
                "auth": {"type": "bearer", "token": "${BEARER}"},
            },
        )
        assert isinstance(server, MCPServerStreamableHTTP)
        assert server.headers == {"Authorization": "Bearer s3cret"}

    def test_http_config(self):
        server = _build_server("http", {"url": "http://example.com/mcp"})
        assert isinstance(server, MCPServerStreamableHTTP)

    def test_http_with_bearer_sets_auth_header(self):
        server = _build_server(
            "http",
            {
                "url": "http://example.com/mcp",
                "auth": {"type": "bearer", "token": "secret"},
            },
        )
        assert isinstance(server, MCPServerStreamableHTTP)
        assert server.headers == {"Authorization": "Bearer secret"}

    def test_websocket_url_rejected(self):
        with pytest.raises(ValueError, match="WebSocket transport"):
            _build_server("ws", {"url": "ws://example.com/mcp"})

    def test_wss_url_rejected(self):
        with pytest.raises(ValueError, match="WebSocket transport"):
            _build_server("wss", {"url": "wss://example.com/mcp"})

    def test_empty_config_raises(self):
        with pytest.raises(ValueError, match="command.*url"):
            _build_server("empty", {})


class TestSetupAndTeardown:
    async def test_no_config_returns_empty(self, app_config):
        meta = await setup_mcp_servers()
        assert meta == {}
        assert mcp_servers == {}
        await teardown_mcp_servers()

    async def test_stdio_server_loads_tools(self, app_config, mcp_server_config):
        app_config.set("mcpServers", {"test_server": mcp_server_config["stdio"]})
        try:
            meta = await setup_mcp_servers()
            assert "test_server" in meta
            names = {m["name"] for m in meta["test_server"]}
            assert {"oracle", "puzzle_solver"}.issubset(names)
            assert "test_server" in mcp_servers
        finally:
            await teardown_mcp_servers()

    async def test_failed_server_init_is_skipped(self, app_config):
        app_config.set(
            "mcpServers",
            {"broken": {"command": "nonexistent-command-xyz"}},
        )
        try:
            meta = await setup_mcp_servers()
            assert meta == {}
            assert mcp_servers == {}
        finally:
            await teardown_mcp_servers()

    async def test_bad_config_is_skipped_and_logged(self, app_config):
        import oterm.log

        app_config.set(
            "mcpServers",
            {
                "ws-bad": {"url": "ws://localhost/mcp"},
                "good": {"command": "mcp", "args": ["--help"]},
            },
        )
        before = len(oterm.log.log_lines)
        try:
            await setup_mcp_servers()
            messages = [msg for _, msg in oterm.log.log_lines[before:]]
            assert any("WebSocket" in m for m in messages)
            # The "good" server fails init (mcp --help isn't a valid MCP server),
            # but failure shouldn't crash the overall setup.
        finally:
            await teardown_mcp_servers()
