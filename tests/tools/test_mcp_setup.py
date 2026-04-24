from oterm.tools.mcp.setup import (
    mcp_clients,
    setup_mcp_servers,
    teardown_mcp_servers,
)


class TestSetupAndTeardown:
    async def test_no_config_returns_empty(self, app_config):
        tool_defs = await setup_mcp_servers()
        assert tool_defs == {}

    async def test_stdio_server_loads_tools(self, app_config, mcp_server_config):
        mcp_clients.clear()
        app_config.set("mcpServers", {"test_server": mcp_server_config["stdio"]})

        try:
            tool_defs = await setup_mcp_servers()

            assert "test_server" in tool_defs
            names = {t["name"] for t in tool_defs["test_server"]}
            assert {"oracle", "puzzle_solver"}.issubset(names)
        finally:
            await teardown_mcp_servers()
            mcp_clients.clear()

    async def test_failed_server_init_is_skipped(self, app_config):
        mcp_clients.clear()
        app_config.set(
            "mcpServers",
            {"broken": {"command": "nonexistent-command-xyz"}},
        )

        tool_defs = await setup_mcp_servers()
        assert tool_defs == {}
