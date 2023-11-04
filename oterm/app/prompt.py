from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea

# TODO: Handle paste event on Input widget and switch to multiline


class FlexibleInput(Widget):
    is_multiline = reactive(False, layout=True)
    text = reactive("", layout=True)

    @dataclass
    class Submitted(Message):
        input: "FlexibleInput"
        value: str

        @property
        def control(self) -> "FlexibleInput":
            return self.input

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

    def clear(self) -> None:
        self.text = ""
        self.query_one("#promptInput", Input).value = ""
        self.query_one("#promptArea", TextArea).text = ""

    def focus(self, scroll_visible: bool = True) -> "FlexibleInput":
        if self.is_multiline:
            self.query_one("#promptArea", TextArea).focus(scroll_visible)
        else:
            self.query_one("#promptInput", Input).focus(scroll_visible)
        return self

    @on(Input.Submitted, "#promptInput")
    def on_input_submitted(self, event: Input.Submitted):
        self.post_message(self.Submitted(self, event.input.value))
        event.stop()
        event.prevent_default()

    @on(Button.Pressed, "#toggle-multiline")
    def on_toggle_multiline(self):
        self.is_multiline = not self.is_multiline
        input = self.query_one("#promptInput", Input)
        textarea = self.query_one("#promptArea", TextArea)
        if self.is_multiline:
            textarea.text = self.text
            textarea.visible = True
            input.visible = False
            self.add_class("multiline")
            self.remove_class("singleline")
        else:
            input.value = self.text
            textarea.visible = False
            input.visible = True
            self.add_class("singleline")
            self.remove_class("multiline")
        self.focus()
        self.refresh()

    @on(Input.Changed, "#promptInput")
    def on_input_changed(self, event: Input.Changed):
        self.text = event.input.value

    @on(TextArea.Changed, "#promptArea")
    def on_area_changed(self, event: TextArea.Changed):
        self.text = event.text_area.text

    @on(Button.Pressed, "#post")
    async def on_post(self):
        input = self.query_one("#promptInput", Input)
        input.value = self.text
        self.post_message(self.Submitted(self, self.text))

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(
                id="promptInput",
                placeholder="Message Ollama…",
            )
            yield TextArea(id="promptArea")
            with Horizontal(id="button-container"):
                yield Button("post", id="post", variant="primary")
                yield Button("↕", id="toggle-multiline", variant="success")


class PromptWidget(Static):
    text = reactive("")

    def compose(self) -> ComposeResult:
        yield FlexibleInput(text=self.text, classes="singleline")
