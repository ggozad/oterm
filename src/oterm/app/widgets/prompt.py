from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, TextArea

from oterm.app.image_browser import ImageSelect
from oterm.app.widgets.image import ImageAdded

MAX_PROMPT_LINES = 10


class PostableTextArea(TextArea):
    """TextArea that auto-grows with content, submits on Enter, newline on Shift+Enter or Ctrl+M."""

    BINDINGS = TextArea.BINDINGS + [
        Binding(
            key="enter",
            action="submit",
            description="submit",
            show=True,
            key_display=None,
            priority=True,
        ),
        Binding(
            key="shift+enter",
            action="newline",
            description="newline",
            show=True,
            key_display=None,
            priority=True,
            id="newline",
        ),
        Binding(
            key="ctrl+m",
            action="newline",
            description="newline",
            show=False,
            key_display=None,
            priority=True,
        ),
    ]

    @dataclass
    class Submitted(Message):
        input: "PostableTextArea"
        value: str

        @property
        def control(self) -> "PostableTextArea":
            return self.input

    def on_mount(self) -> None:
        self.soft_wrap = True
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        line_count = max(self.wrapped_document.height, 1)
        self.styles.height = min(line_count, MAX_PROMPT_LINES)

    def action_submit(self) -> None:
        self.post_message(PostableTextArea.Submitted(self, self.text))

    def action_newline(self) -> None:
        self.insert("\n")


class FlexibleInput(Widget):
    text = reactive("")

    BINDINGS = [
        Binding("ctrl+i", "add_image", "add image", id="add.image"),
    ]

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
        textarea = self.query_one("#promptArea", PostableTextArea)
        textarea.show_line_numbers = False
        textarea.focus()

    def clear(self) -> None:
        self.text = ""
        self.query_one("#promptArea", PostableTextArea).text = ""

    def focus(self, scroll_visible=True) -> "FlexibleInput":
        self.query_one("#promptArea", PostableTextArea).focus()
        return self

    def watch_text(self):
        try:
            textarea = self.query_one("#promptArea", PostableTextArea)
            if textarea.text != self.text:
                textarea.text = self.text
        except NoMatches:
            pass

    def action_add_image(self) -> None:
        async def on_image_selected(image) -> None:
            if image is None:
                return
            path, b64 = image
            self.post_message(ImageAdded(path, b64))

        screen = ImageSelect()
        self.app.push_screen(screen, on_image_selected)

    @on(PostableTextArea.Submitted, "#promptArea")
    def on_textarea_submitted(self, event: PostableTextArea.Submitted):
        self.post_message(self.Submitted(self, event.input.text))
        event.stop()
        event.prevent_default()

    @on(TextArea.Changed, "#promptArea")
    def on_area_changed(self, event: TextArea.Changed):
        self.text = event.text_area.text
        if isinstance(event.text_area, PostableTextArea):
            event.text_area._resize_to_content()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("❯", id="promptMarker")
            yield PostableTextArea(id="promptArea")
