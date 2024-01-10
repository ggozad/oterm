from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.widgets import Markdown, Static
from textual.widgets._markdown import MarkdownFence as BaseMarkdownFence


class MarkdownFence(BaseMarkdownFence):
    """A MarkdownFence that responds to the app's dark mode."""

    def __init__(self, markdown: Markdown, code: str, lexer: str) -> None:
        super().__init__(markdown, code, lexer)
        self.theme = "solarized-dark" if self.app.dark else "solarized-light"

    def _retheme(self) -> None:
        """Swap between a dark and light theme when the mode changes."""
        self.theme = "solarized-dark" if self.app.dark else "solarized-light"
        code_block = self.query_one(".code-block", Static)
        code_block.renderable = Syntax(
            self.code,
            lexer=self.lexer,
            word_wrap=False,
            indent_guides=True,
            padding=(1, 2),
            theme=self.theme,
        )

    def on_mount(self) -> None:
        """Watch app theme switching."""
        self.watch(self.app, "dark", self._retheme)

    def compose(self) -> ComposeResult:
        yield Static(
            Syntax(
                self.code,
                lexer=self.lexer,
                word_wrap=False,
                indent_guides=True,
                padding=(1, 2),
                theme=self.theme,
            ),
            expand=True,
            shrink=False,
            classes="code-block",
        )
