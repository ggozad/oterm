from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Input, Static


class PromptWidget(Static):
    text = reactive("")

    def compose(self) -> ComposeResult:
        """Human prompt."""
        with Horizontal():
            yield Input(
                placeholder="Message Ollama…",
                id="promptInput",
            )
