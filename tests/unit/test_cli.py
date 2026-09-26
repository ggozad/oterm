import pytest

from oterm.cli.oterm import upgrade_db


class TestUpgradeDb:
    async def test_tools_load_before_store_and_tear_down_after(
        self, tmp_data_dir, monkeypatch
    ):
        """The 0.22.0 upgrade reads the connected servers, so ordering matters."""
        import oterm.cli.oterm as cli_mod
        import oterm.tools as tools_mod
        import oterm.tools.mcp.setup as mcp_setup_mod

        calls: list[str] = []

        async def fake_load_tools():
            calls.append("load_tools")

        async def fake_teardown():
            calls.append("teardown")

        class _FakeStore:
            @classmethod
            async def get_store(cls):
                calls.append("get_store")

        monkeypatch.setattr(tools_mod, "load_tools", fake_load_tools)
        monkeypatch.setattr(mcp_setup_mod, "teardown_mcp_servers", fake_teardown)
        monkeypatch.setattr(cli_mod, "Store", _FakeStore)

        await upgrade_db()

        assert calls == ["load_tools", "get_store", "teardown"]

    async def test_servers_torn_down_when_upgrade_fails(
        self, tmp_data_dir, monkeypatch
    ):
        import oterm.cli.oterm as cli_mod
        import oterm.tools as tools_mod
        import oterm.tools.mcp.setup as mcp_setup_mod

        torn_down: list[bool] = []

        async def fake_load_tools():
            return None

        async def fake_teardown():
            torn_down.append(True)

        class _BrokenStore:
            @classmethod
            async def get_store(cls):
                raise RuntimeError("boom")

        monkeypatch.setattr(tools_mod, "load_tools", fake_load_tools)
        monkeypatch.setattr(mcp_setup_mod, "teardown_mcp_servers", fake_teardown)
        monkeypatch.setattr(cli_mod, "Store", _BrokenStore)

        with pytest.raises(RuntimeError, match="boom"):
            await upgrade_db()
        assert torn_down == [True]


class TestConfigOption:
    def test_prints_the_config_once(self):
        from typer.testing import CliRunner

        from oterm.cli.oterm import cli

        result = CliRunner().invoke(cli, ["--config"])

        assert result.exit_code == 0
        assert "OTERM_DATA_DIR" in result.output
        assert not result.output.endswith("\n\n")

    def test_masks_the_ollama_api_key(self, monkeypatch):
        from typer.testing import CliRunner

        import oterm.config
        from oterm.cli.oterm import cli

        monkeypatch.setattr(oterm.config.envConfig, "OLLAMA_API_KEY", "sk-secret")

        result = CliRunner().invoke(cli, ["--config"])

        assert result.exit_code == 0
        assert "sk-secret" not in result.output
        assert "OLLAMA_API_KEY='***'" in result.output


class TestHelp:
    def test_every_option_is_described(self):
        from typer.testing import CliRunner

        from oterm.cli.oterm import cli

        output = CliRunner().invoke(cli, ["--help"]).output

        for text in (
            "Print the version",
            "Apply pending database upgrades",
            "Print the environment settings",
            "Print the path of the chat database",
            "Print the data directory",
        ):
            assert text in output, text
