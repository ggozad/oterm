import json
from enum import Enum

import pyperclip
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Static

from oterm.app.prompt import FlexibleInput
from oterm.ollama import OllamaLLM


class Author(Enum):
    USER = "me"
    OLLAMA = "ollama"


class ChatContainer(Widget):
    ollama = OllamaLLM()
    messages: reactive[list[tuple[Author, str]]] = reactive([])
    chat_name: str
    system: str | None
    template: str | None

    def __init__(
        self,
        *children: Widget,
        db_id: int,
        chat_name: str,
        model: str = "nous-hermes:13b",
        context: list[int] = [],
        messages: list[tuple[Author, str]] = [],
        system: str | None = None,
        template: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.ollama = OllamaLLM(
            model=model, context=context, template=template, system=system
        )  # We do this to reset the context
        self.chat_name = chat_name
        self.db_id = db_id
        self.messages = messages
        self.system = system
        self.template = template

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()
        if self.messages:
            message_container = self.query_one("#messageContainer")
            for author, message in self.messages:
                chat_item = ChatItem()
                chat_item.text = message
                chat_item.author = author
                message_container.mount(chat_item)
            message_container.scroll_end()

    @on(FlexibleInput.Submitted)
    async def on_submit(self, event: FlexibleInput.Submitted) -> None:
        message = event.value
        input = event.input
        message_container = self.query_one("#messageContainer")

        input.clear()
        input.disabled = True
        self.messages.append((Author.USER, message))
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
        self.messages.append((Author.OLLAMA, response))
        loading.remove()
        input.disabled = False
        input.focus()

        # Save to db
        await self.app.store.save_context(  # type: ignore
            id=self.db_id,
            context=json.dumps(self.ollama.context),
        )
        await self.app.store.save_message(  # type: ignore
            chat_id=self.db_id,
            author=Author.USER.value,
            text=message,
        )
        await self.app.store.save_message(  # type: ignore
            chat_id=self.db_id,
            author=Author.OLLAMA.value,
            text=response,
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"model: {self.ollama.model}", id="info")
            yield Vertical(id="messageContainer")
            yield FlexibleInput("", id="prompt", classes="singleline")


class ChatItem(Widget):
    text: reactive[str] = reactive("")
    author: Author

    @on(Click)
    async def on_click(self, event: Click) -> None:
        pyperclip.copy(self.text)
        widget = self.query_one(".text", Static)
        widget.styles.animate("opacity", 0.5, duration=0.1)
        widget.styles.animate("opacity", 1.0, duration=0.1, delay=0.1)

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
            yield Static(self.author.value, classes="author", markup=False)
            yield Static(self.text, classes="text", markup=False)
