from enum import Enum

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, LoadingIndicator, Static

from oterm.app.prompt import PromptWidget
from oterm.ollama import OllamaLLM


class Author(Enum):
    USER = "me"
    OLLAMA = "ollama"


class ChatContainer(Widget):
    ollama = OllamaLLM()
    messages: reactive[list[tuple[str, Author]]] = reactive([])

    def __init__(
        self,
        *children: Widget,
        model: str = "nous-hermes:13b",
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.ollama = OllamaLLM(model=model)  # We do this to reset the context

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
        chat_item = ChatItem()
        chat_item.text = message
        chat_item.author = Author.USER
        message_container.mount(chat_item)

        chat_item = ChatItem()
        chat_item.author = Author.OLLAMA
        message_container.mount(chat_item)
        loading = LoadingIndicator()
        message_container.mount(loading)
        message_container.scroll_end()

        response = ""
        async for text in self.ollama.stream(message):
            response = text
            chat_item.text = text
            message_container.scroll_end()
        self.messages.append((response, Author.OLLAMA))
        loading.remove()
        input.disabled = False
        input.focus()


class ChatItem(Widget):
    text: reactive[str] = reactive("")
    author: Author

    def watch_text(self, text: str) -> None:
        try:
            widget = self.query_one(".text", Static)
            if widget:
                widget.update(text)
        except NoMatches:
            pass

    def compose(self) -> ComposeResult:
        """A chat item."""
        with Horizontal(classes=f"{self.author.name} chatItem"):
            yield Static(self.author.value, classes="author")
            yield Static(self.text, classes="text")
