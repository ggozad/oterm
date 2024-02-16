import asyncio
import json
from enum import Enum
from pathlib import Path
from typing import Literal

import pyperclip
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    LoadingIndicator,
    Markdown,
    Static,
    TabbedContent,
)

from oterm.app.chat_edit import ChatEdit
from oterm.app.chat_export import ChatExport, slugify
from oterm.app.chat_rename import ChatRename
from oterm.app.widgets.image import ImageAdded
from oterm.app.widgets.prompt import FlexibleInput
from oterm.ollama import OllamaLLM


class Author(Enum):
    USER = "me"
    OLLAMA = "ollama"


class ChatContainer(Widget):
    ollama = OllamaLLM()
    messages: reactive[list[tuple[Author, str]]] = reactive([])
    chat_name: str
    system: str | None
    format: Literal["json"] | None
    images: list[tuple[Path, str]] = []

    BINDINGS = [
        Binding("ctrl+e", "edit_chat", "edit", priority=True),
        Binding("ctrl+s", "export", "export", priority=True),
        ("ctrl+r", "rename_chat", "rename"),
        ("ctrl+x", "forget_chat", "forget"),
        Binding(
            "escape", "cancel_inference", "cancel inference", show=False, priority=True
        ),
    ]

    def __init__(
        self,
        *children: Widget,
        db_id: int,
        chat_name: str,
        model: str = "nous-hermes:13b",
        context: list[int] = [],
        messages: list[tuple[Author, str]] = [],
        system: str | None = None,
        format: Literal["json"] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.ollama = OllamaLLM(
            model=model,
            context=context,
            system=system,
            format=format,
        )  # We do this to reset the context
        self.chat_name = chat_name
        self.db_id = db_id
        self.messages = messages
        self.system = system
        self.format = format
        self.loaded = False

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()

    async def load_messages(self) -> None:
        if self.loaded:
            return
        message_container = self.query_one("#messageContainer")
        for author, message in self.messages:
            chat_item = ChatItem()
            chat_item.text = message
            chat_item.author = author
            await message_container.mount(chat_item)
        message_container.scroll_end()
        self.loaded = True

    @on(FlexibleInput.Submitted)
    async def on_submit(self, event: FlexibleInput.Submitted) -> None:
        message = event.value
        input = event.input
        message_container = self.query_one("#messageContainer")

        if not message.strip():
            input.clear()
            input.focus()
            return

        async def response_task() -> None:
            input.clear()
            self.messages.append((Author.USER, message))
            user_chat_item = ChatItem()
            user_chat_item.text = message
            user_chat_item.author = Author.USER
            message_container.mount(user_chat_item)

            response_chat_item = ChatItem()
            response_chat_item.author = Author.OLLAMA
            message_container.mount(response_chat_item)
            loading = LoadingIndicator()
            message_container.mount(loading)
            message_container.scroll_end()

            try:
                response = ""
                async for text in self.ollama.stream(
                    message, [img for _, img in self.images]
                ):
                    response = text
                    response_chat_item.text = text
                    message_container.scroll_end()
                self.messages.append((Author.OLLAMA, response))
                self.images = []

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
            except asyncio.CancelledError:
                user_chat_item.remove()
                response_chat_item.remove()
                input.text = message
            finally:
                loading.remove()
                input.focus()

        self.inference_task = asyncio.create_task(response_task())

    def key_escape(self) -> None:
        if hasattr(self, "inference_task"):
            self.inference_task.cancel()

    async def action_edit_chat(self) -> None:
        async def on_model_select(model_info: str) -> None:
            model: dict = json.loads(model_info)
            self.system = model.get("system")
            self.format = model.get("format")
            await self.app.store.edit_chat(
                id=self.db_id,
                name=self.chat_name,
                system=model["system"],
                format=model["format"],
            )
            _, _, _, context, _, _ = await self.app.store.get_chat(self.db_id)
            self.ollama = OllamaLLM(
                model=model["name"],
                context=context,
                system=model["system"],
                format=model["format"],
            )

        screen = ChatEdit()
        screen.model_name = self.ollama.model

        await self.app.push_screen(screen, on_model_select)
        screen.edit_mode = True
        screen.select_model(self.ollama.model)

        if self.system:
            screen.system = self.system

    async def action_export(self) -> None:
        screen = ChatExport()
        screen.chat_id = self.db_id
        screen.file_name = f"{slugify(self.chat_name)}.md"
        self.app.push_screen(screen)

    async def action_rename_chat(self) -> None:
        async def on_chat_rename(name: str) -> None:
            tabs = self.app.query_one(TabbedContent)
            await self.app.store.rename_chat(self.db_id, name)
            tabs.get_tab(f"chat-{self.db_id}").update(name)

        screen = ChatRename()
        screen.old_name = self.chat_name
        self.app.push_screen(screen, on_chat_rename)

    async def action_forget_chat(self) -> None:
        tabs = self.app.query_one(TabbedContent)
        await self.app.store.delete_chat(self.db_id)
        tabs.remove_pane(tabs.active)

    @on(ImageAdded)
    def on_image_added(self, ev: ImageAdded) -> None:
        self.images.append((ev.path, ev.image))
        message_container = self.query_one("#messageContainer")
        notification = Notification()
        notification.message = f"Image {ev.path} added."
        message_container.mount(notification)
        message_container.scroll_end()

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
        try:
            pyperclip.copy(self.text)
        except pyperclip.PyperclipException:
            # https://pyperclip.readthedocs.io/en/latest/index.html#not-implemented-error
            return
        widgets = self.query(".text")
        for widget in widgets:
            widget.styles.animate("opacity", 0.5, duration=0.1)
            widget.styles.animate("opacity", 1.0, duration=0.1, delay=0.1)

    async def watch_text(self, text: str) -> None:
        text = self.text
        try:
            jsn = json.loads(text)
            if isinstance(jsn, dict):
                text = f"```json\n{self.text}\n```"
        except json.JSONDecodeError:
            pass

        txt_widget = self.query_one(".text", Markdown)
        await txt_widget.update(text)

    def compose(self) -> ComposeResult:
        """A chat item."""
        mrk_down = Markdown(self.text, classes="text")
        mrk_down.code_dark_theme = "solarized-dark"
        mrk_down.code_light_theme = "solarized-light"
        with Horizontal(classes=f"{self.author.name} chatItem"):
            yield Static(self.author.value, classes="author", markup=False)
            yield mrk_down


class Notification(Widget):
    message: reactive[str] = reactive("")

    def compose(self) -> ComposeResult:
        yield Static(self.message, classes="notification")
