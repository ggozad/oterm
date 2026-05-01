from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Label, RichLog

from oterm.log import log_lines
from oterm.utils import debounce


class LogViewer(ModalScreen[str]):
    line_count: reactive[int] = reactive(0)

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save_logs", "Save logs", priority=True),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    def action_save_logs(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path.cwd() / f"oterm-logs-{timestamp}.txt"
        with path.open("w", encoding="utf-8") as file:
            for group, line in log_lines:
                file.write(f"[{group.name}] {line}\n")
        self.notify(f"Logs exported to {path}")

    @debounce(0.5)
    async def log_update(self) -> None:
        widget = self.query_one(RichLog)
        new_lines = log_lines[self.line_count :]
        self.line_count += len(new_lines)
        for group, line in new_lines:
            widget.write(f"[b]{group.name}[/b] - {line}")
        await self.log_update()

    async def on_screen_resume(self) -> None:
        await self.log_update()

    def compose(self) -> ComposeResult:
        with Container(id="log-viewer", classes="screen-container full-height"):
            yield Label("oterm logs", classes="title")
            yield RichLog(
                highlight=True,
                markup=True,
                auto_scroll=True,
                wrap=True,
            )
