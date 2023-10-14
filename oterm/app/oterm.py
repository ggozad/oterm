from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, TabbedContent, TabPane

from oterm.app.chat import ChatContainer
from oterm.app.model_selection import ModelSelection
from oterm.app.splash import SplashScreen


class OTerm(App):
    TITLE = "oTerm"
    SUB_TITLE = "A terminal-based Ollama client."
    CSS_PATH = "oterm.tcss"
    BINDINGS = [
        ("n", "new_chat", "new chat"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
    ]
    SCREENS = {
        "splash": SplashScreen(),
        "model_selection": ModelSelection(),
    }

    tab_count = 0

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

    def action_quit(self) -> None:
        return self.exit()

    def action_new_chat(self) -> None:
        def on_model_select(model: str) -> None:
            self.tab_count += 1
            tabs = self.query_one(TabbedContent)
            pane = TabPane(
                f"chat #{self.tab_count} - {model}", id=f"chat-{self.tab_count}"
            )
            pane.compose_add_child(ChatContainer(model=model))
            tabs.add_pane(pane)
            tabs.active = f"chat-{self.tab_count}"

        self.push_screen("model_selection", on_model_select)

    async def on_mount(self) -> None:
        self.action_new_chat()
        await self.push_screen("splash")

    def compose(self) -> ComposeResult:
        yield Header()
        yield TabbedContent(id="tabs")
        yield Footer()


app = OTerm()
