import pytest
from pydantic_ai.mcp import MCPServerSSE, MCPServerStdio, MCPServerStreamableHTTP

from oterm.tools.mcp.setup import (
    _build_servers,
    mcp_servers,
    setup_mcp_servers,
    teardown_mcp_servers,
)


class TestBuildServers:
    def test_stdio_config(self):
        built = _build_servers(
            {"stdio": {"command": "mcp", "args": ["run", "x"], "env": {"FOO": "bar"}}}
        )
        server = built["stdio"]
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["LOGLEVEL"] == "ERROR"
        assert env["FOO"] == "bar"

    def test_stdio_does_not_inherit_parent_env(self, monkeypatch):
        """Secure default: parent env (PATH, secrets, etc.) is not leaked."""
        monkeypatch.setenv("SECRET_TOKEN", "leak-me")
        built = _build_servers({"stdio": {"command": "mcp", "args": []}})
        server = built["stdio"]
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert "SECRET_TOKEN" not in env
        assert "PATH" not in env

    def test_stdio_user_env_overrides_logging_overrides(self):
        built = _build_servers(
            {"stdio": {"command": "mcp", "args": [], "env": {"LOGLEVEL": "DEBUG"}}}
        )
        server = built["stdio"]
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["LOGLEVEL"] == "DEBUG"

    def test_http_config(self):
        built = _build_servers({"http": {"url": "http://example.com/mcp"}})
        assert isinstance(built["http"], MCPServerStreamableHTTP)

    def test_http_with_authorization_header(self):
        built = _build_servers(
            {
                "http": {
                    "url": "http://example.com/mcp",
                    "headers": {"Authorization": "Bearer secret"},
                }
            }
        )
        server = built["http"]
        assert isinstance(server, MCPServerStreamableHTTP)
        assert server.headers == {"Authorization": "Bearer secret"}

    def test_url_ending_in_sse_resolves_to_sse_server(self):
        built = _build_servers({"sse": {"url": "http://example.com/sse"}})
        assert isinstance(built["sse"], MCPServerSSE)

    def test_sampling_is_disabled(self):
        built = _build_servers(
            {
                "stdio": {"command": "mcp", "args": []},
                "http": {"url": "http://example.com/mcp"},
            }
        )
        assert built["stdio"].allow_sampling is False
        assert built["http"].allow_sampling is False

    def test_websocket_url_rejected(self):
        with pytest.raises(ValueError, match="WebSocket transport"):
            _build_servers({"ws": {"url": "ws://example.com/mcp"}})

    def test_wss_url_rejected(self):
        with pytest.raises(ValueError, match="WebSocket transport"):
            _build_servers({"wss": {"url": "wss://example.com/mcp"}})

    def test_env_var_substitution_in_env_values(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "shh")
        built = _build_servers(
            {
                "stdio": {
                    "command": "mcp",
                    "args": [],
                    "env": {"GITHUB_TOKEN": "${MY_TOKEN}"},
                }
            }
        )
        server = built["stdio"]
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["GITHUB_TOKEN"] == "shh"

    def test_env_var_substitution_in_command_and_args(self, monkeypatch):
        monkeypatch.setenv("MCP_BIN", "/opt/bin/mcp")
        built = _build_servers(
            {
                "stdio": {
                    "command": "${MCP_BIN}",
                    "args": ["--config", "${MCP_BIN}.conf"],
                }
            }
        )
        server = built["stdio"]
        assert isinstance(server, MCPServerStdio)
        assert server.command == "/opt/bin/mcp"
        assert list(server.args) == ["--config", "/opt/bin/mcp.conf"]

    def test_env_var_substitution_with_default(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        built = _build_servers(
            {
                "stdio": {
                    "command": "mcp",
                    "args": [],
                    "env": {"DEFAULTED": "${MISSING_VAR:-fallback}"},
                }
            }
        )
        server = built["stdio"]
        assert isinstance(server, MCPServerStdio)
        env = server.env or {}
        assert env["DEFAULTED"] == "fallback"

    def test_env_var_substitution_missing_raises(self, monkeypatch):
        monkeypatch.delenv("UNDEFINED_VAR", raising=False)
        with pytest.raises(ValueError, match="UNDEFINED_VAR"):
            _build_servers(
                {
                    "stdio": {
                        "command": "mcp",
                        "args": [],
                        "env": {"X": "${UNDEFINED_VAR}"},
                    }
                }
            )

    def test_env_var_substitution_in_authorization_header(self, monkeypatch):
        monkeypatch.setenv("BEARER", "s3cret")
        built = _build_servers(
            {
                "http": {
                    "url": "http://x/mcp",
                    "headers": {"Authorization": "Bearer ${BEARER}"},
                }
            }
        )
        server = built["http"]
        assert isinstance(server, MCPServerStreamableHTTP)
        assert server.headers == {"Authorization": "Bearer s3cret"}


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
            {"broken": {"command": "nonexistent-command-xyz", "args": []}},
        )
        try:
            meta = await setup_mcp_servers()
            assert meta == {}
            assert mcp_servers == {}
        finally:
            await teardown_mcp_servers()

    async def test_websocket_in_config_logs_and_skips_all(self, app_config):
        """Validation failures for the whole config block are logged once."""
        import oterm.log

        app_config.set(
            "mcpServers",
            {"ws-bad": {"url": "ws://localhost/mcp"}},
        )
        before = len(oterm.log.log_lines)
        try:
            meta = await setup_mcp_servers()
            assert meta == {}
            messages = [msg for _, msg in oterm.log.log_lines[before:]]
            assert any("WebSocket" in m for m in messages)
        finally:
            await teardown_mcp_servers()

    async def test_unexpected_exception_during_build_is_logged(
        self, app_config, monkeypatch
    ):
        """Non-ValueError exceptions during _build_servers are caught and logged."""
        import oterm.log
        import oterm.tools.mcp.setup as setup_mod

        def boom(_raw):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(setup_mod, "_build_servers", boom)
        app_config.set("mcpServers", {"x": {"url": "http://example.com/mcp"}})
        before = len(oterm.log.log_lines)
        try:
            meta = await setup_mcp_servers()
            assert meta == {}
            messages = [msg for _, msg in oterm.log.log_lines[before:]]
            assert any("could not be parsed" in m for m in messages)
        finally:
            await teardown_mcp_servers()
