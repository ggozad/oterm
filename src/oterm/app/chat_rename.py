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

    def action_cancel(self) -> None:
        self.dismiss()

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        if event.value:
            self.dismiss(event.value)

    def compose(self) -> ComposeResult:
        with Container(id="chat-rename-container"):
            yield Label("Rename chat", classes="title")
            yield Input(id="chat-name-input", value=self.old_name)
