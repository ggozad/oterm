from textual.events import Key
from textual.widgets import TextArea as BaseTextArea


class TextArea(BaseTextArea):
    """A TextArea that responds to the app's dark mode.
    This might be potentially fixed after https://github.com/Textualize/textual/issues/3997 is resolved.
    In addition we ignore the tab key to allow it to move along the focus chain.
    """

    def _retheme(self) -> None:
        """Swap between a dark and light theme when the mode changes."""
        self.theme = "vscode_dark" if self.app.dark else "github_light"

    def on_mount(self) -> None:
        """Watch app theme switching."""
        self.watch(self.app, "dark", self._retheme)

    async def _on_key(self, event: Key) -> None:
        """Allow tab to move along the focus chain."""
        if event.key == "tab":
            event.prevent_default()
            self.screen.focus_next()
