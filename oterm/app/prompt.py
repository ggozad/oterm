from dataclasses import dataclass
from typing import cast

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea


class PastableInput(Input):
    def _on_paste(self, event: events.Paste) -> None:
        if event.text:
            self.insert_text_at_cursor(event.text)
            lines = event.text.splitlines()
            if len(lines) > 1:
                parent = cast(FlexibleInput, self.app.query(".prompt").first())
                parent.toggle_multiline()


class FlexibleInput(Widget):
    is_multiline = reactive(False)
    text = reactive("")

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
        input = self.query_one("#promptInput", PastableInput)
        textarea = self.query_one("#promptArea", TextArea)
        textarea.show_line_numbers = False
        if self.is_multiline:
            textarea.focus()
        else:
            input.focus()

    def clear(self) -> None:
        self.text = ""
        self.query_one("#promptInput", PastableInput).value = ""
        self.query_one("#promptArea", TextArea).text = ""

    def focus(self) -> "FlexibleInput":
        if self.is_multiline:
            self.query_one("#promptArea", TextArea).focus()
        else:
            self.query_one("#promptInput", PastableInput).focus()
        return self

    @on(PastableInput.Submitted, "#promptInput")
    def on_input_submitted(self, event: Input.Submitted):
        self.post_message(self.Submitted(self, event.input.value))
        event.stop()
        event.prevent_default()

    def watch_is_multiline(self, value: bool) -> None:
        input = self.query_one("#promptInput", PastableInput)
        textarea = self.query_one("#promptArea", TextArea)
        if self.is_multiline:
            textarea.text = self.text
            self.add_class("multiline")
            self.remove_class("singleline")
        else:
            input.value = self.text
            self.add_class("singleline")
            self.remove_class("multiline")
        self.focus()

    @on(Button.Pressed, "#toggle-multiline")
    def on_toggle_multiline_pressed(self):
        self.toggle_multiline()

    def toggle_multiline(self):
        print("TOGGLE MULTILINE")
        self.is_multiline = not self.is_multiline

    @on(PastableInput.Changed, "#promptInput")
    def on_input_changed(self, event: PastableInput.Changed):
        self.text = event.input.value

    @on(TextArea.Changed, "#promptArea")
    def on_area_changed(self, event: TextArea.Changed):
        self.text = event.text_area.text

    @on(Button.Pressed, "#post")
    async def on_post(self):
        input = self.query_one("#promptInput", PastableInput)
        input.value = self.text
        self.post_message(self.Submitted(self, self.text))

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield PastableInput(
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
        yield FlexibleInput(text=self.text, classes="prompt")
