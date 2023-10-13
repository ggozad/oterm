from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from oterm.app.chat import ChatContainer


class OTerm(App):
    TITLE = "oTerm"
    SUB_TITLE = "A terminal-based Ollama client."
    CSS_PATH = "oterm.tcss"
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"), ("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ChatContainer()
        yield Footer()

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark

    def action_quit(self) -> None:
        return self.exit()


app = OTerm()
