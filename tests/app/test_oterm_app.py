import pytest
from textual.widgets import TabbedContent, TabPane

from oterm.types import ChatModel, MessageModel


@pytest.fixture(autouse=True)
def stub_network(monkeypatch):
    """Keep OTerm.on_mount from touching the network or spawning MCP servers."""
    import oterm.app.oterm as oterm_mod
    import oterm.utils as utils_mod

    async def _up_to_date():
        from importlib import metadata

        from packaging.version import parse

        v = parse(metadata.version("oterm"))
        return True, v, v

    async def _no_mcp():
        return {}

    monkeypatch.setattr(utils_mod, "is_up_to_date", _up_to_date)
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

            app.action_cycle_chat(1)
            await pilot.pause()
            assert tabs.active == f"chat-{ids[1]}"

            app.action_cycle_chat(-1)
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
            app.action_cycle_chat(1)


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
            assert await store.get_chat(cm.id) is None

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
        await store.save_message(MessageModel(chat_id=cm.id, role="user", text="hi"))

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.action_clear_chat()
            await pilot.pause()
            assert await store.get_messages(cm.id) == []


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
        import oterm.tools as tools_mod

        def fake_tool() -> str:
            """Sample."""
            return "x"

        from oterm.tools import make_tool_def

        called: list[tuple] = []

        def fake_discover():
            return [make_tool_def(fake_tool)]

        async def fake_mcp_setup():
            called.append(("mcp",))
            return {}

        original_discover = tools_mod.discover_tools
        original_builtins = tools_mod.builtin_tools
        tools_mod.discover_tools = fake_discover  # ty: ignore[invalid-assignment]
        oterm_mod.setup_mcp_servers = fake_mcp_setup  # ty: ignore[invalid-assignment]
        try:
            from oterm.app.oterm import OTerm

            app = OTerm()
            async with app.run_test() as pilot:
                await pilot.pause()
                names = {t["name"] for t in tools_mod.builtin_tools}
                assert "fake_tool" in names
                assert called
        finally:
            tools_mod.discover_tools = original_discover
            tools_mod.builtin_tools = original_builtins


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


class TestActionDelegates:
    """OTerm.action_* methods that just forward to ChatContainer.action_*."""

    async def test_edit_chat_delegates_to_active_container(
        self, tmp_data_dir, app_config, stub_network, store, monkeypatch
    ):
        from oterm.app.oterm import OTerm
        from oterm.app.widgets.chat import ChatContainer

        app_config.set("splash-screen", False)
        cm = ChatModel(name="c", model="m")
        cm.id = await store.save_chat(cm)

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()

            called: list[bool] = []

            def spy(self):
                called.append(True)

            monkeypatch.setattr(ChatContainer, "action_edit_chat", spy)
            await app.action_edit_chat()
            await pilot.pause()
            assert called == [True]

    async def test_rename_chat_delegates(
        self, tmp_data_dir, app_config, stub_network, store, monkeypatch
    ):
        from oterm.app.oterm import OTerm
        from oterm.app.widgets.chat import ChatContainer

        app_config.set("splash-screen", False)
        cm = ChatModel(name="c", model="m")
        cm.id = await store.save_chat(cm)

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()

            called: list[bool] = []

            def spy(self):
                called.append(True)

            monkeypatch.setattr(ChatContainer, "action_rename_chat", spy)
            await app.action_rename_chat()
            await pilot.pause()
            assert called == [True]

    async def test_regenerate_last_message_delegates(
        self, tmp_data_dir, app_config, stub_network, store, monkeypatch
    ):
        from oterm.app.oterm import OTerm
        from oterm.app.widgets.chat import ChatContainer

        app_config.set("splash-screen", False)
        cm = ChatModel(name="c", model="m")
        cm.id = await store.save_chat(cm)

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()

            called: list[bool] = []

            async def spy(self):
                called.append(True)

            monkeypatch.setattr(ChatContainer, "action_regenerate_llm_message", spy)
            await app.action_regenerate_last_message()
            await pilot.pause()
            assert called == [True]

    async def test_action_delegates_are_noop_without_active_pane(self, fresh_app):
        from textual.widgets import TabbedContent

        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            for pane in list(tabs.query("TabPane")):
                await tabs.remove_pane(pane.id or "")
            await pilot.pause()

            # None of these should raise.
            await app.action_edit_chat()
            await app.action_rename_chat()
            await app.action_export_chat()
            await app.action_regenerate_last_message()
            await app.action_clear_chat()
            await app.action_prompt_history()

    async def test_prompt_history_delegates_to_active_container(
        self, tmp_data_dir, app_config, stub_network, store, monkeypatch
    ):
        from oterm.app.oterm import OTerm
        from oterm.app.widgets.chat import ChatContainer

        app_config.set("splash-screen", False)
        cm = ChatModel(name="c", model="m")
        cm.id = await store.save_chat(cm)

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()

            called: list[bool] = []

            async def spy(self):
                called.append(True)

            monkeypatch.setattr(ChatContainer, "action_history", spy)
            await app.action_prompt_history()
            await pilot.pause()
            assert called == [True]


class TestNoneIdGuards:
    """Chats lacking a database id (e.g. from a failed save) are skipped."""

    async def test_delete_with_id_none_is_noop(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        from textual.widgets import TabbedContent, TabPane

        from oterm.app.oterm import OTerm
        from oterm.app.widgets.chat import ChatContainer

        app_config.set("splash-screen", False)
        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            # Replace the auto-created chat with one whose chat_model.id is None.
            for pane in list(tabs.query("TabPane")):
                await tabs.remove_pane(pane.id or "")
            await pilot.pause()
            cm = ChatModel(model="m", provider="ollama")
            assert cm.id is None
            pane = TabPane("orphan", id="chat-orphan")
            pane.compose_add_child(ChatContainer(chat_model=cm, messages=[]))
            await tabs.add_pane(pane)
            tabs.active = "chat-orphan"
            await pilot.pause()

            await app.action_delete_chat()
            await pilot.pause()
            # Pane is preserved because the guard skipped the delete.
            assert tabs.tab_count == 1

    async def test_export_with_id_none_is_noop(
        self, tmp_data_dir, app_config, stub_network, store
    ):
        from textual.widgets import TabbedContent, TabPane

        from oterm.app.oterm import OTerm
        from oterm.app.widgets.chat import ChatContainer

        app_config.set("splash-screen", False)
        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            tabs = app.query_one(TabbedContent)
            for pane in list(tabs.query("TabPane")):
                await tabs.remove_pane(pane.id or "")
            await pilot.pause()
            cm = ChatModel(model="m", provider="ollama")
            pane = TabPane("orphan", id="chat-orphan")
            pane.compose_add_child(ChatContainer(chat_model=cm, messages=[]))
            await tabs.add_pane(pane)
            tabs.active = "chat-orphan"
            await pilot.pause()

            original_screen = app.screen
            await app.action_export_chat()
            await pilot.pause()
            # Without a chat id, no ChatExport screen is pushed.
            assert app.screen is original_screen

    async def test_saved_chat_with_id_none_is_skipped_on_load(
        self, tmp_data_dir, app_config, stub_network, monkeypatch
    ):
        from textual.widgets import TabbedContent

        from oterm.store.store import Store

        app_config.set("splash-screen", False)

        async def fake_get_chats(self):
            return [ChatModel(id=None, name="orphan", model="m")]

        monkeypatch.setattr(Store, "get_chats", fake_get_chats)

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            # The orphan chat is skipped; no panes added during the load loop.
            tabs = app.query_one(TabbedContent)
            assert tabs.tab_count == 0


class TestThemeEdgeCases:
    async def test_no_theme_in_config_does_not_set_theme(
        self, tmp_data_dir, app_config, stub_network
    ):
        app_config.set("splash-screen", False)
        # An empty-string theme falls through the `if theme:` guard.
        app_config.set("theme", "")

        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Textual default takes over; nothing was forced.
            assert app.theme  # whatever default is, app started cleanly

    async def test_theme_change_to_same_value_does_not_rewrite_config(
        self, fresh_app, app_config, monkeypatch
    ):
        app = fresh_app
        async with app.run_test() as pilot:
            await pilot.pause()
            current_theme = app.theme
            app_config.set("theme", current_theme)

            writes: list[tuple] = []
            original_set = app_config.set

            def track_set(key, value):
                writes.append((key, value))
                original_set(key, value)

            monkeypatch.setattr(app_config, "set", track_set)

            # on_theme_change is the watcher; calling it directly with the same
            # value must short-circuit (no config write).
            app.on_theme_change(current_theme, current_theme)
            await pilot.pause()
            assert writes == []


class TestPerformChecks:
    async def test_outdated_version_notifies(
        self, tmp_data_dir, app_config, stub_network, monkeypatch
    ):
        import oterm.app.oterm as oterm_mod

        async def _outdated():
            from packaging.version import parse

            return False, parse("0.0.0"), parse("99.0.0")

        monkeypatch.setattr(oterm_mod, "is_up_to_date", _outdated)

        app_config.set("splash-screen", False)
        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            # perform_checks fires as part of on_mount after splash_done
            for _ in range(20):
                await pilot.pause()
                if any("available" in n.message for n in list(app._notifications)):
                    break
            assert any("available" in n.message for n in list(app._notifications))


class TestTheme:
    async def test_dark_theme_from_config(self, tmp_data_dir, app_config, stub_network):
        app_config.set("splash-screen", False)
        app_config.set("theme", "dark")
        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "textual-dark"

    async def test_light_theme_from_config(
        self, tmp_data_dir, app_config, stub_network
    ):
        app_config.set("splash-screen", False)
        app_config.set("theme", "light")
        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "textual-light"

    async def test_custom_named_theme_from_config(
        self, tmp_data_dir, app_config, stub_network
    ):
        app_config.set("splash-screen", False)
        app_config.set("theme", "solarized-dark")
        from oterm.app.oterm import OTerm

        app = OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == "solarized-dark"


class TestKeymap:
    async def test_keymap_remaps_new_chat_binding(
        self, tmp_data_dir, app_config, stub_network, monkeypatch
    ):
        import oterm.app.oterm as oterm_mod

        calls: list[bool] = []
        monkeypatch.setattr(
            oterm_mod.OTerm,
            "action_new_chat",
            lambda self: calls.append(True),
        )

        app_config.set("splash-screen", False)
        app_config.set("keymap", {"new.chat": "f5"})

        app = oterm_mod.OTerm()
        async with app.run_test() as pilot:
            await pilot.pause()
            calls.clear()  # ignore the on_mount auto-new-chat call
            await pilot.press("f5")
            await pilot.pause()
            assert calls == [True]


class TestSplashCallback:
    async def test_splash_dismissal_triggers_post_splash_flow(
        self, tmp_data_dir, app_config, stub_network, monkeypatch
    ):
        """With splash on, on_mount defers the first-chat + perform_checks flow until splash dismisses."""
        from textual.screen import Screen

        import oterm.app.oterm as oterm_mod

        class _StubSplash(Screen):
            async def on_mount(self):
                self.dismiss("")

        monkeypatch.setattr(oterm_mod, "splash", _StubSplash())

        new_chat_calls: list[bool] = []
        monkeypatch.setattr(
            oterm_mod.OTerm,
            "action_new_chat",
            lambda self: new_chat_calls.append(True),
        )

        app_config.set("splash-screen", True)

        app = oterm_mod.OTerm()
        async with app.run_test() as pilot:
            for _ in range(30):
                await pilot.pause()
                if new_chat_calls:
                    break
            assert new_chat_calls == [True]


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
                "Show logs",
            ):
                assert title in cmds
