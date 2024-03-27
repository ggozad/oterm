import pyperclip
import textual.widgets._markdown as markdown
from textual import on
from textual.events import Click


class MarkdownFence(markdown.MarkdownFence):
    @on(Click)
    async def on_click(self, event: Click) -> None:
        event.stop()
        try:
            pyperclip.copy(self.code)
        except pyperclip.PyperclipException:
            # https://pyperclip.readthedocs.io/en/latest/index.html#not-implemented-error
            return

        self.styles.animate("opacity", 0.5, duration=0.1)
        self.styles.animate("opacity", 1.0, duration=0.1, delay=0.1)


markdown.MarkdownFence = MarkdownFence
