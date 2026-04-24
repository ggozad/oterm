import pytest
from textual.widgets import TabbedContent, TabPane

from oterm.types import ChatModel, MessageModel


@pytest.fixture(autouse=True)
def stub_network(monkeypatch):
    """Keep OTerm.on_mount from touching the network or spawning MCP servers."""
    import oterm.app.oterm as oterm_mod
    import oterm.utils as utils_mod

    async def _ok():
        return True

    async def _up_to_date():
        from importlib import metadata

        from packaging.version import parse

        v = parse(metadata.version("oterm"))
        return True, v, v

    async def _no_mcp():
        return {}, {}

    monkeypatch.setattr(utils_mod, "check_ollama", _ok)
    monkeypatch.setattr(utils_mod, "is_up_to_date", _up_to_date)
    monkeypatch.setattr(oterm_mod, "check_ollama", _ok)
    monkeypatch.setattr(oterm_mod, "is_up_to_date", _up_to_date)
    monkeypatch.setattr(oterm_mod, "setup_mcp_servers", _no_mcp)

    async def _no_teardown():
        return None

    monkeypatch.setattr(oterm_mod, "teardown_mcp_servers", _no_teardown)


@pytest.fixture
def fresh_app(tmp_data_dir, app_config, stub_network):
    """Build a fresh OTerm app wired to an isolated data dir, splash off."""
    app_config.set("splash-screen", False)

    from oterm.app.oterm import OTerm

    return OTerm()


class TestStartup:
    async def test_splash_off_creates_first_chat(self, fresh_app, store, monkeypatch):
        """On empty store, on_mount triggers action_new_chat."""
        called: list[bool] = []

        from oterm.app.oterm import OTerm

        original = OTerm.action_new_chat

        def spy(self):
            called.append(True)
            return original(self)

        monkeypatch.setattr(OTerm, "action_new_chat", spy)

        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            assert called == [True]

    async def test_existing_chats_loaded_into_tabs(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        app_config.set("splash-screen", False)

        chat_a = ChatModel(name="alpha", model="m")
        chat_a.id = await store.save_chat(chat_a)
        chat_b = ChatModel(name="beta", model="m")
        chat_b.id = await store.save_chat(chat_b)

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            assert tabs.tab_count == 2


class TestCycleChat:
    async def test_cycle_forward_and_back(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        app_config.set("splash-screen", False)
        ids = []
        for n in ("a", "b", "c"):
            cm = ChatModel(name=n, model="m")
            cm.id = await store.save_chat(cm)
            ids.append(cm.id)

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            tabs.active = f"chat-{ids[0]}"
            await pilot.pause()

            await app.action_cycle_chat(1)
            await pilot.pause()
            assert tabs.active == f"chat-{ids[1]}"

            await app.action_cycle_chat(-1)
            await pilot.pause()
            assert tabs.active == f"chat-{ids[0]}"

    async def test_cycle_with_no_active_pane_is_noop(self, fresh_app, monkeypatch):
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            # Remove all panes to simulate no active pane.
            for pane in list(tabs.query(TabPane)):
                await tabs.remove_pane(pane.id or "")
            await pilot.pause()
            assert tabs.active_pane is None

            # Should return silently with no exception
            await app.action_cycle_chat(1)


class TestDeleteChat:
    async def test_delete_removes_pane_and_db_row(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        app_config.set("splash-screen", False)
        cm = ChatModel(name="doomed", model="m")
        cm.id = await store.save_chat(cm)

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            assert tabs.tab_count == 1

            await app.action_delete_chat()
            await pilot.pause()

            assert tabs.tab_count == 0
            assert await store.get_chat(cm.id) is None  # type: ignore[arg-type]

    async def test_delete_without_active_pane_is_noop(self, fresh_app):
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            for pane in list(tabs.query(TabPane)):
                await tabs.remove_pane(pane.id or "")
            await pilot.pause()

            await app.action_delete_chat()  # silently no-op


class TestClearChat:
    async def test_clear_on_active_chat_wipes_messages(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        app_config.set("splash-screen", False)
        cm = ChatModel(name="c", model="m")
        cm.id = await store.save_chat(cm)
        await store.save_message(MessageModel(chat_id=cm.id, role="user", text="hi"))  # type: ignore[arg-type]

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_clear_chat()
            await pilot.pause()
            assert await store.get_messages(cm.id) == []  # type: ignore[arg-type]


class TestExportChat:
    async def test_export_pushes_screen_when_active_pane_has_chat(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        from oterm.app.chat_export import ChatExport

        app_config.set("splash-screen", False)
        cm = ChatModel(name="C One", model="m")
        cm.id = await store.save_chat(cm)

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_export_chat()
            await pilot.pause()
            assert isinstance(app.screen, ChatExport)


class TestPullModel:
    async def test_pull_model_pushes_screen(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        from oterm.app.pull_model import PullModel

        app_config.set("splash-screen", False)
        cm = ChatModel(name="c", model="llama3")
        cm.id = await store.save_chat(cm)

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_pull_model()
            await pilot.pause()
            assert isinstance(app.screen, PullModel)
            assert app.screen.model == "llama3"


class TestShowLogs:
    async def test_show_logs_pushes_screen(self, fresh_app):
        from oterm.app.log_viewer import LogViewer

        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_show_logs()
            await pilot.pause()
            assert isinstance(app.screen, LogViewer)


class TestThemePersistence:
    async def test_theme_change_persists_to_app_config(self, fresh_app, app_config):
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            app.theme = "textual-light"
            await pilot.pause()
            assert app_config.get("theme") == "textual-light"


class TestLoadTools:
    async def test_discovers_entry_point_tools(
        self, tmp_data_dir, app_config, stub_network
    ):
        import oterm.app.oterm as oterm_mod

        def fake_tool() -> str:
            """Sample."""
            return "x"

        from oterm.tools import make_tool_def

        called: list[tuple] = []

        def fake_discover():
            return [make_tool_def(fake_tool)]

        async def fake_mcp_setup():
            called.append(("mcp",))
            return {}, {}

        import oterm.tools as tools_mod

        monkeypatch_tools = tools_mod.available_tool_defs.copy()
        tools_mod.available_tool_defs.clear()
        try:
            # Stub discover_tools via the imported module.
            import oterm.tools

            original_discover = oterm.tools.discover_tools
            oterm.tools.discover_tools = fake_discover  # ty: ignore[invalid-assignment]
            oterm_mod.setup_mcp_servers = fake_mcp_setup  # ty: ignore[invalid-assignment]

            from oterm.app.oterm import OTerm

            app = OTerm()
            async with app.run_test() as pilot:
                await pilot.pause()
                # on_mount already called load_tools once.
                assert "oterm" in tools_mod.available_tool_defs
                names = {t["name"] for t in tools_mod.available_tool_defs["oterm"]}
                assert "fake_tool" in names
                assert called  # fake_mcp_setup was invoked at least once
        finally:
            oterm.tools.discover_tools = original_discover
            tools_mod.available_tool_defs.clear()
            tools_mod.available_tool_defs.update(monkeypatch_tools)


class TestNewChat:
    async def test_new_chat_from_modal_creates_tab(
        self, tmp_data_dir, app_config, stub_network, store, monkeypatch
    ):
        """action_new_chat awaits a ChatEdit modal; feed back a valid JSON payload."""
        app_config.set("splash-screen", False)

        from oterm.app.oterm import OTerm

        chat_json = ChatModel(model="llama3", provider="ollama").model_dump_json(
            exclude_none=True
        )

        async def fake_push_screen_wait(self, screen):
            return chat_json

        monkeypatch.setattr(OTerm, "push_screen_wait", fake_push_screen_wait)

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            initial = app.query_one(TabbedContent).tab_count

            app.action_new_chat()
            # The @work decorator runs the action in a worker; give it time.
            for _ in range(30):
                await pilot.pause()
                if app.query_one(TabbedContent).tab_count > initial:
                    break
            assert app.query_one(TabbedContent).tab_count == initial + 1
            chats = await store.get_chats()
            assert any(c.model == "llama3" for c in chats)

    async def test_new_chat_cancelled_modal_noop(self, fresh_app, store, monkeypatch):
        from oterm.app.oterm import OTerm

        async def fake_push_screen_wait(self, screen):
            return None

        monkeypatch.setattr(OTerm, "push_screen_wait", fake_push_screen_wait)
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            initial = app.query_one(TabbedContent).tab_count
            app.action_new_chat()
            for _ in range(10):
                await pilot.pause()
            assert app.query_one(TabbedContent).tab_count == initial


class TestQuit:
    async def test_ctrl_q_exits(self, fresh_app):
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.is_running
            await pilot.press("ctrl+q")
            # run_test teardown will exit; we just verify the binding works.
            # After action_quit, app.exit() has been called.
            for _ in range(10):
                await pilot.pause()
                if not app.is_running:
                    break
            assert not app.is_running


class TestSystemCommands:
    async def test_system_commands_includes_all_actions(self, fresh_app):
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            cmds = [c.title for c in app.get_system_commands(app.screen)]
            for title in (
                "New chat",
                "Edit chat parameters",
                "Rename chat",
                "Clear chat",
                "Delete chat",
                "Export chat",
                "Regenerate last message",
                "Use MCP prompt",
                "Pull model",
                "Show logs",
            ):
                assert title in cmds
