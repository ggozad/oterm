from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class ChatRename(ModalScreen[str]):
    old_name: str = ""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, old_name: str) -> None:
        super().__init__()
        self.old_name = old_name

    def action_cancel(self) -> None:
        self.dismiss()

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        if event.value:
            self.dismiss(event.value)

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container short"):
            yield Label("Rename chat", classes="title")
            yield Input(id="chat-name-input", value=self.old_name)
