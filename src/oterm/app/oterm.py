from collections.abc import Iterable
from functools import partial

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
from oterm.app.widgets.empty_state import EmptyState
from oterm.config import appConfig
from oterm.providers import get_available_providers
from oterm.store.store import Store
from oterm.tools import load_tools
from oterm.tools.mcp.setup import teardown_mcp_servers
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
        Binding("ctrl+n", "new_chat", "new chat", id="new.chat"),
        Binding("ctrl+t", "toggle_thinking", "toggle thinking", id="toggle.thinking"),
        Binding("ctrl+o", "copy_message", "copy message", id="copy.message"),
        Binding("ctrl+l", "show_logs", "show logs", id="show.logs"),
        Binding("ctrl+f", "go_to_chat", "go to chat", id="go.to.chat"),
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
            "Toggle thinking",
            "Turns thinking mode on or off for the current chat",
            self.action_toggle_thinking,
        )
        yield SystemCommand(
            "Copy message",
            "Copies the last message of the current chat to the clipboard",
            self.action_copy_message,
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
            "Prompt history",
            "Shows previously sent prompts in the current chat",
            self.action_prompt_history,
        )
        yield SystemCommand(
            "Show logs", "Shows the logs of the app", self.action_show_logs
        )
        yield SystemCommand(
            "Go to chat", "Switches to a chat picked by name", self.action_go_to_chat
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
        if tabs.active not in pane_ids:  # pragma: no cover
            return
        idx = pane_ids.index(tabs.active)
        self._open_chat(pane_ids[(idx + change) % len(pane_ids)])

    def action_go_to_chat(self) -> None:
        tabs = self.query_one(TabbedContent)
        self.search_commands(
            [
                (
                    str(tabs.get_tab(pane).label),
                    partial(self._open_chat, pane.id or ""),
                )
                for pane in tabs.query(TabPane)
            ],
            placeholder="Search chats…",
        )

    def _open_chat(self, pane_id: str) -> None:
        tabs = self.query_one(TabbedContent)
        tabs.active = pane_id
        tabs.get_pane(pane_id).query_one("#prompt").focus()

    @work
    async def action_new_chat(self) -> None:
        store = await Store.get_store()
        last_provider = await store.get_last_provider()
        chat_model = (
            ChatModel(provider=last_provider)
            if last_provider in get_available_providers()
            else ChatModel()
        )
        edited = await self.push_screen_wait(ChatEdit(chat_model))
        if edited is None:
            return
        chat_model = edited
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
        self._update_empty_state()

    def _active_chat(self) -> ChatContainer | None:
        pane = self.query_one(TabbedContent).active_pane
        return pane.query_one(ChatContainer) if pane is not None else None

    async def action_edit_chat(self) -> None:
        if chat := self._active_chat():
            chat.action_edit_chat()

    async def action_toggle_thinking(self) -> None:
        if chat := self._active_chat():
            chat.action_toggle_thinking()

    async def action_copy_message(self) -> None:
        if chat := self._active_chat():
            chat.action_copy_message()

    async def action_rename_chat(self) -> None:
        if chat := self._active_chat():
            chat.action_rename_chat()

    async def action_clear_chat(self) -> None:
        if chat := self._active_chat():
            await chat.action_clear_chat()

    async def action_delete_chat(self) -> None:
        chat = self._active_chat()
        if chat is None or chat.chat_model.id is None:
            return
        store = await Store.get_store()
        await store.delete_chat(chat.chat_model.id)
        tabs = self.query_one(TabbedContent)
        await tabs.remove_pane(tabs.active)
        self.notify(f"Deleted {chat.chat_model.name}", severity="information")
        self._update_empty_state()

    async def action_export_chat(self) -> None:
        chat = self._active_chat()
        if chat is None or chat.chat_model.id is None:
            return
        self.push_screen(
            ChatExport(
                chat_id=chat.chat_model.id,
                file_name=f"{slugify(chat.chat_model.name)}.md",
            )
        )

    async def action_regenerate_last_message(self) -> None:
        if chat := self._active_chat():
            await chat.action_regenerate_llm_message()

    async def action_prompt_history(self) -> None:
        if chat := self._active_chat():
            await chat.action_history()

    async def action_show_logs(self) -> None:
        from oterm.app.log_viewer import LogViewer

        screen = LogViewer()
        self.push_screen(screen)

    @work(exclusive=True, group="checks")
    async def perform_checks(self) -> None:
        up_to_date, _, latest = await is_up_to_date()
        if not up_to_date:
            self.notify(
                f"[b]oterm[/b] version [i]{latest}[/i] is available, please update.",
                severity="warning",
            )

    async def on_mount(self) -> None:
        self.register_theme(solarized_dark)
        # Tools load first: the store upgrade that qualifies MCP tool names by
        # server needs the connected servers' tool lists.
        await load_tools()
        store = await Store.get_store()
        theme = appConfig.get("theme")
        if theme:  # pragma: no branch
            if theme == "dark":
                self.theme = "textual-dark"
            elif theme == "light":
                self.theme = "textual-light"
            else:
                self.theme = theme
        self.watch(self.app, "theme", self.on_theme_change, init=False)

        saved_chats = await store.get_chats()
        keymap = appConfig.get("keymap")
        if keymap:
            self.set_keymap(keymap)

        async def on_splash_done(message) -> None:
            tabs = self.query_one(TabbedContent)
            for chat_model in saved_chats:
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
            self._update_empty_state()
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
        yield EmptyState(id="empty-state")
        yield Footer()

    def _update_empty_state(self) -> None:
        has_chats = self.query_one(TabbedContent).tab_count > 0
        self.query_one(TabbedContent).display = has_chats
        self.query_one(EmptyState).display = not has_chats


app = OTerm()
