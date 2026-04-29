from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static


class EmptyState(Container):
    DEFAULT_CSS = """
    EmptyState { align: center middle; }
    EmptyState Static { text-align: center; }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "[b]Welcome to oterm![/b]\n\n"
            "Press [b]Ctrl+N[/b] to start a new chat,\n"
            "or [b]Ctrl+P[/b] to open the command palette."
        )
