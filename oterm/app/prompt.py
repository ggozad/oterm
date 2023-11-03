from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea

# TODO: Handle past event on Input widget and potentially switch to multiline


class FlexibleInput(Widget):
    is_multiline = reactive(False, layout=True)
    text = reactive("", layout=True)

    def __init__(self, text, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.text = text

    def on_mount(self) -> None:
        input = self.query_one("#promptInput", Input)
        textarea = self.query_one("#promptArea", TextArea)
        textarea.show_line_numbers = False
        if self.is_multiline:
            input.visible = False
            textarea.focus()
        else:
            textarea.visible = False
            input.focus()

    @on(Button.Pressed, "#toggle-multiline")
    def on_toggle_multiline(self):
        self.is_multiline = not self.is_multiline
        input = self.query_one("#promptInput", Input)
        textarea = self.query_one("#promptArea", TextArea)
        if self.is_multiline:
            textarea.text = input.value
            textarea.visible = True
            textarea.focus()
            input.visible = False
        else:
            input.value = textarea.text
            textarea.visible = False
            input.focus()
            input.visible = True

    def compose(self) -> ComposeResult:
        print("compose", self.is_multiline)
        with Horizontal():
            yield Input(
                id="promptInput",
                placeholder="Message Ollama… ",
            )
            yield TextArea(id="promptArea")
            with Horizontal(id="button-container"):
                yield Button("post", id="post", variant="primary")
                yield Button("↕", id="toggle-multiline", variant="success")


class PromptWidget(Static):
    text = reactive("")

    def compose(self) -> ComposeResult:
        """Human prompt."""
        yield FlexibleInput(text=self.text)
