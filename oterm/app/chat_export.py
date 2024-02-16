from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class ChatExport(ModalScreen[str]):
    chat_id: int
    file_name: str = ""
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        if not event.value:
            return

        self.dismiss()

    def compose(self) -> ComposeResult:
        with Container(id="chat-export-container"):
            yield Label("Export chat", classes="title")
            yield Input(id="chat-name-input", value=self.file_name)
