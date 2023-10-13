from enum import Enum

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, LoadingIndicator, Static
from textual.worker import get_current_worker

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
        input.clear()

        message_container = self.query_one("#messageContainer")

        self.messages.append((message, Author.USER))
        message_container.mount(ChatItem(message, Author.USER))
        loading = LoadingIndicator()
        message_container.mount(loading)
        message_container.scroll_end()
        input.disabled = True
        self.get_response(message)

    @work(exclusive=True, thread=True)
    def get_response(self, prompt: str) -> None:
        response = self.ollama.completion(prompt)
        worker = get_current_worker()
        if not worker.is_cancelled:
            self.app.call_from_thread(self.add_ollama_response, response)
            return

    def add_ollama_response(self, response: str) -> None:
        message_container = self.query_one("#messageContainer")
        self.messages.append((response, Author.OLLAMA))
        loading_indicator = self.query_one(LoadingIndicator)
        loading_indicator.remove()
        message_container.mount(ChatItem(response, Author.OLLAMA))
        input = self.query_one("#promptInput")
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
