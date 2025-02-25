import textual.widgets._markdown as markdown
from textual import on
from textual.events import Click


class MarkdownFence(markdown.MarkdownFence):
    @on(Click)
    async def on_click(self, event: Click) -> None:
        event.stop()
        self.app.copy_to_clipboard(self.code)
        self.styles.animate("opacity", 0.5, duration=0.1)
        self.styles.animate("opacity", 1.0, duration=0.1, delay=0.1)


markdown.MarkdownFence = MarkdownFence
