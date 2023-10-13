from enum import Enum

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, LoadingIndicator, Static

from oterm.app.prompt import PromptWidget
from oterm.ollama import OlammaLLM


class Author(Enum):
    USER = "me"
    OLLAMA = "ollama"


class ChatContainer(Widget):
    ollama = OlammaLLM()
    messages: reactive[list[tuple[str, Author]]] = reactive([])

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Vertical(id="messageContainer")
            yield PromptWidget(id="prompt")

    @on(Input.Submitted)
    async def on_submit(self, event: Input.Submitted) -> None:
        message = event.value
        input = event.input
        message_container = self.query_one("#messageContainer")

        input.clear()
        input.disabled = True
        self.messages.append((message, Author.USER))
        message_container.mount(ChatItem(message, Author.USER))
        loading = LoadingIndicator()
        message_container.mount(loading)
        message_container.scroll_end()

        response = await self.ollama.completion(message)
        self.messages.append((response, Author.OLLAMA))
        loading.remove()
        message_container.mount(ChatItem(response, Author.OLLAMA))
        input.disabled = False
        input.focus()


class ChatItem(Static):
    text: str = ""
    author: Author

    def __init__(self, text="", author=Author.USER, **kwargs):
        super().__init__(**kwargs)
        self.author = author
        self.text = text

    def compose(self) -> ComposeResult:
        """A chat item."""
        with Horizontal(classes=f"{self.author.name} chatItem"):
            yield Static(self.author.value, classes="author")
            yield Static(self.text, classes="text")
