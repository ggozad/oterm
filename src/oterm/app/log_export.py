from datetime import datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Label

from oterm.log import log_lines


class LogExport(ModalScreen[str]):
    file_name: str = ""
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, file_name: str = "") -> None:
        super().__init__()
        if not file_name:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            file_name = f"oterm-logs-{timestamp}.txt"
        self.file_name = file_name

    def action_cancel(self) -> None:
        self.dismiss()

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        if not event.value:
            return

        with open(event.value, "w", encoding="utf-8") as file:
            for group, line in log_lines:
                file.write(f"[{group.name}] {line}\n")

        self.app.notify(f"Logs exported to {event.value}")
        self.dismiss()

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container short"):
            yield Label("Export logs", classes="title")
            yield Input(id="log-file-input", value=self.file_name)
