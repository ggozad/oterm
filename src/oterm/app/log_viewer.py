from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Label, RichLog

from oterm.log import log_lines
from oterm.utils import debounce


class LogViewer(ModalScreen[str]):
    line_count: reactive[int] = reactive(0)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

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
