from collections.abc import Iterable

from textual import on, work
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, TabbedContent, TabPane

from oterm.app.chat_edit import ChatEdit
from oterm.app.chat_export import ChatExport, slugify
from oterm.app.splash import splash
from oterm.app.themes.solarized_dark import solarized_dark
from oterm.app.widgets.chat import ChatContainer
from oterm.config import appConfig
from oterm.store.store import Store
from oterm.tools.mcp.setup import setup_mcp_servers, teardown_mcp_servers
from oterm.types import ChatModel
from oterm.utils import is_up_to_date


class OTerm(App):
    TITLE = "oterm"
    SUB_TITLE = "the terminal LLM client."
    CSS_PATH = "oterm.tcss"
    BINDINGS = [
        Binding(
            "ctrl+tab", "cycle_chat(+1)", "next chat", id="next.chat", priority=True
        ),
        Binding(
            "ctrl+shift+tab",
            "cycle_chat(-1)",
            "prev chat",
            id="prev.chat",
            priority=True,
        ),
        Binding("ctrl+backspace", "delete_chat", "delete chat", id="delete.chat"),
        Binding("ctrl+n", "new_chat", "new chat", id="new.chat"),
        Binding("ctrl+l", "show_logs", "show logs", id="show.logs"),
        Binding("ctrl+q", "quit", "quit", id="quit"),
    ]

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield from super().get_system_commands(screen)
        yield SystemCommand("New chat", "Creates a new chat", self.action_new_chat)
        yield SystemCommand(
            "Edit chat parameters",
            "Allows to redefine model parameters and system prompt",
            self.action_edit_chat,
        )
        yield SystemCommand(
            "Rename chat", "Renames the current chat", self.action_rename_chat
        )
        yield SystemCommand(
            "Clear chat", "Clears the current chat", self.action_clear_chat
        )
        yield SystemCommand(
            "Delete chat", "Deletes the current chat", self.action_delete_chat
        )
        yield SystemCommand(
            "Export chat",
            "Exports the current chat as Markdown (in the current working directory)",
            self.action_export_chat,
        )
        yield SystemCommand(
            "Regenerate last message",
            "Regenerates the last assistant message",
            self.action_regenerate_last_message,
        )
        yield SystemCommand(
            "Show logs", "Shows the logs of the app", self.action_show_logs
        )

    async def action_quit(self) -> None:
        self.log("Quitting...")
        await teardown_mcp_servers()
        return self.exit()

    def action_cycle_chat(self, change: int) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        pane_ids = [pane.id or "" for pane in tabs.query(TabPane)]
        if tabs.active not in pane_ids:
            return
        idx = pane_ids.index(tabs.active)
        tabs.active = pane_ids[(idx + change) % len(pane_ids)]

    @work
    async def action_new_chat(self) -> None:
        store = await Store.get_store()
        model_info: str | None = await self.push_screen_wait(ChatEdit())
        if not model_info:
            return

        chat_model = ChatModel.model_validate_json(model_info)
        tabs = self.query_one(TabbedContent)
        tab_count = tabs.tab_count

        name = f"chat #{tab_count + 1} - {chat_model.model}"
        chat_model.name = name

        id = await store.save_chat(chat_model)
        chat_model.id = id

        pane = TabPane(name, id=f"chat-{id}")
        pane.compose_add_child(
            ChatContainer(
                chat_model=chat_model,
                messages=[],
            )
        )
        await tabs.add_pane(pane)
        tabs.active = f"chat-{id}"

    async def action_edit_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        chat = tabs.active_pane.query_one(ChatContainer)
        chat.action_edit_chat()

    async def action_rename_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        chat = tabs.active_pane.query_one(ChatContainer)
        chat.action_rename_chat()

    async def action_clear_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        chat = tabs.active_pane.query_one(ChatContainer)
        await chat.action_clear_chat()

    async def action_delete_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        chat = tabs.active_pane.query_one(ChatContainer)
        store = await Store.get_store()

        if chat.chat_model.id is not None:
            await store.delete_chat(chat.chat_model.id)
            await tabs.remove_pane(tabs.active)
            self.notify(f"Deleted {chat.chat_model.name}", severity="information")

    async def action_export_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        chat = tabs.active_pane.query_one(ChatContainer)

        if chat.chat_model.id is not None:
            screen = ChatExport(
                chat_id=chat.chat_model.id,
                file_name=f"{slugify(chat.chat_model.name)}.md",
            )
            self.push_screen(screen)

    async def action_regenerate_last_message(self) -> None:
        tabs = self.query_one(TabbedContent)
        if tabs.active_pane is None:
            return
        chat = tabs.active_pane.query_one(ChatContainer)
        await chat.action_regenerate_llm_message()

    async def action_show_logs(self) -> None:
        from oterm.app.log_viewer import LogViewer

        screen = LogViewer()
        self.push_screen(screen)

    async def load_tools(self):
        from oterm.tools import available_tool_defs, discover_tools

        entry_point_tools = discover_tools()
        if entry_point_tools:
            available_tool_defs["oterm"] = entry_point_tools
        mcp_tool_defs = await setup_mcp_servers()
        available_tool_defs.update(mcp_tool_defs)

    @work(exclusive=True)
    async def perform_checks(self) -> None:
        up_to_date, _, latest = await is_up_to_date()
        if not up_to_date:
            self.notify(
                f"[b]oterm[/b] version [i]{latest}[/i] is available, please update.",
                severity="warning",
            )

    async def on_mount(self) -> None:
        self.register_theme(solarized_dark)
        store = await Store.get_store()
        theme = appConfig.get("theme")
        if theme:
            if theme == "dark":
                self.theme = "textual-dark"
            elif theme == "light":
                self.theme = "textual-light"
            else:
                self.theme = theme
        self.watch(self.app, "theme", self.on_theme_change, init=False)

        saved_chats = await store.get_chats()
        # Apply any remap of key bindings.
        keymap = appConfig.get("keymap")
        if keymap:
            self.set_keymap(keymap)

        await self.load_tools()

        async def on_splash_done(message) -> None:
            if not saved_chats:
                self.action_new_chat()
            else:
                tabs = self.query_one(TabbedContent)
                for chat_model in saved_chats:
                    # Only process chats with a valid ID
                    if chat_model.id is not None:
                        messages = await store.get_messages(chat_model.id)
                        container = ChatContainer(
                            chat_model=chat_model,
                            messages=messages,
                        )
                        pane = TabPane(
                            chat_model.name, container, id=f"chat-{chat_model.id}"
                        )
                        tabs.add_pane(pane)
            self.perform_checks()

        if appConfig.get("splash-screen"):
            self.push_screen(splash, callback=on_splash_done)
        else:
            await on_splash_done("")

    def on_theme_change(self, old_value: str, new_value: str) -> None:
        if appConfig.get("theme") != new_value:
            appConfig.set("theme", new_value)

    @work
    @on(TabbedContent.TabActivated)
    async def on_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        container = event.pane.query_one(ChatContainer)
        await container.load_messages()

    def compose(self) -> ComposeResult:
        yield Header()
        yield TabbedContent(id="tabs")
        yield Footer()


app = OTerm()
