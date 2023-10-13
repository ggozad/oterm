from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabPane, TabbedContent

from oterm.app.chat import ChatContainer


class OTerm(App):
    TITLE = "oTerm"
    SUB_TITLE = "A terminal-based Ollama client."
    CSS_PATH = "oterm.tcss"
    BINDINGS = [
        ("n", "new_chat", "new chat"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
    ]

    tab_count = 1

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

    def action_quit(self) -> None:
        return self.exit()

    def action_new_chat(self) -> None:
        self.tab_count += 1
        tabs = self.query_one(TabbedContent)
        pane = TabPane(f"chat #{self.tab_count}", id=f"chat-{self.tab_count}")
        pane.compose_add_child(ChatContainer())
        tabs.add_pane(pane)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs"):
            with TabPane("chat #1", id="chat-1"):
                yield ChatContainer()
        yield Footer()


app = OTerm()
