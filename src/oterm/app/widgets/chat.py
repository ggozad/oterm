import asyncio
import json
import random
from pathlib import Path
from typing import Literal

import pyperclip
from ollama import Message, ResponseError
from textual import on, work
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
from oterm.app.chat_rename import ChatRename
from oterm.app.prompt_history import PromptHistory
from oterm.app.widgets.image import ImageAdded
from oterm.app.widgets.prompt import FlexibleInput
from oterm.ollamaclient import OllamaLLM, Options
from oterm.store.store import Store
from oterm.tools import available as available_tool_defs
from oterm.types import Author, Tool


class ChatContainer(Widget):
    ollama = OllamaLLM()
    messages: reactive[list[tuple[int, Author, str, list[str]]]] = reactive([])
    chat_name: str
    system: str | None
    format: Literal["", "json"]
    parameters: Options
    keep_alive: int = 5
    images: list[tuple[Path, str]] = []
    tools: list[Tool] = []
    BINDINGS = [
        Binding("up", "history", "history"),
        Binding(
            "escape", "cancel_inference", "cancel inference", show=False, priority=True
        ),
    ]

    def __init__(
        self,
        *children: Widget,
        db_id: int,
        chat_name: str,
        model: str = "llama3.2",
        messages: list[tuple[int, Author, str, list[str]]] = [],
        system: str | None = None,
        format: Literal["", "json"] = "",
        parameters: Options,
        keep_alive: int = 5,
        tools: list[Tool] = [],
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)
        history = []
        # This is wrong, the images should be a list of Image objects
        # See https://github.com/ollama/ollama-python/issues/375
        # Temp fix is to do msg.images = images  # type: ignore

        for _, author, message, images in messages:
            msg = Message(
                role="user" if author == Author.USER else "assistant",
                content=message,
            )
            msg.images = images  # type: ignore
            history.append(msg)

        used_tool_defs = [
            tool_def for tool_def in available_tool_defs if tool_def["tool"] in tools
        ]

        self.ollama = OllamaLLM(
            model=model,
            system=system,
            format=format,
            options=parameters,
            keep_alive=keep_alive,
            history=history,  # type: ignore
            tool_defs=used_tool_defs,
        )

        self.chat_name = chat_name
        self.db_id = db_id
        self.messages = messages
        self.system = system
        self.format = format
        self.parameters = parameters
        self.keep_alive = keep_alive
        self.tools = tools
        self.loaded = False
        self.images = []

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()

    async def load_messages(self) -> None:
        if self.loaded:
            return
        message_container = self.query_one("#messageContainer")
        for _, author, message, images in self.messages:
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
            user_chat_item = ChatItem()
            user_chat_item.text = message
            user_chat_item.author = Author.USER
            message_container.mount(user_chat_item)

            response_chat_item = ChatItem()
            response_chat_item.author = Author.OLLAMA
            message_container.mount(response_chat_item)
            loading = LoadingIndicator()
            await message_container.mount(loading)
            message_container.scroll_end()

            try:
                response = ""

                # Ollama does not support streaming with tools, so we need to use completion
                if self.tools:
                    response = await self.ollama.completion(
                        prompt=message, images=[img for _, img in self.images]
                    )
                    response_chat_item.text = response

                else:
                    async for text in self.ollama.stream(
                        message, [img for _, img in self.images]
                    ):
                        response = text
                        response_chat_item.text = text
                if message_container.can_view_partial(response_chat_item):
                    message_container.scroll_end()

                # Save to db
                store = await Store.get_store()
                id = await store.save_message(
                    id=None,
                    chat_id=self.db_id,
                    author=Author.USER.value,
                    text=message,
                    images=[img for _, img in self.images],
                )
                self.messages.append(
                    (id, Author.USER, message, [img for _, img in self.images])
                )

                id = await store.save_message(
                    id=None,
                    chat_id=self.db_id,
                    author=Author.OLLAMA.value,
                    text=response,
                )
                self.messages.append((id, Author.OLLAMA, response, []))
                self.images = []

            except asyncio.CancelledError:
                user_chat_item.remove()
                response_chat_item.remove()
                input.text = message
            except ResponseError as e:
                user_chat_item.remove()
                response_chat_item.remove()
                notification = Notification()
                notification.message = f"There was an error running your request: {e}"
                message_container.mount(notification)
                message_container.scroll_end()

            finally:
                loading.remove()
                input.focus()

        self.inference_task = asyncio.create_task(response_task())

    def key_escape(self) -> None:
        if hasattr(self, "inference_task"):
            self.inference_task.cancel()

    @work
    async def action_edit_chat(self) -> None:
        screen = ChatEdit(
            model=self.ollama.model,
            system=self.system or "",
            parameters=self.parameters,
            json_format=self.format == "json",
            keep_alive=self.keep_alive,
            edit_mode=True,
            tools=self.tools,
        )

        model_info = await self.app.push_screen_wait(screen)
        if model_info is None:
            return
        model: dict = json.loads(model_info)
        self.system = model.get("system")
        self.format = model.get("format", "")
        self.keep_alive = model.get("keep_alive", 5)
        self.parameters = Options(**model.get("parameters", {}))
        self.tools = [Tool(**t) for t in model.get("tools", [])]
        store = await Store.get_store()
        await store.edit_chat(  # type: ignore
            id=self.db_id,
            name=self.chat_name,
            system=model["system"],
            format=model["format"],
            parameters=model["parameters"],
            keep_alive=model["keep_alive"],
            tools=model["tools"],
        )

        # load the history from messages
        history: list[Message] = []
        # This is wrong, the images should be a list of Image objects
        # See https://github.com/ollama/ollama-python/issues/375
        # Temp fix is to do msg.images = images  # type: ignore
        for _, author, message, images in self.messages:
            msg = Message(
                role="user" if author == Author.USER else "assistant",
                content=message,
            )
            msg.images = images  # type: ignore
            history.append(msg)

        used_tool_defs = [
            tool_def
            for tool_def in available_tool_defs
            if tool_def["tool"] in self.tools
        ]

        self.ollama = OllamaLLM(
            model=model["name"],
            system=model["system"],
            format=model["format"],
            options=self.parameters,
            keep_alive=model["keep_alive"],
            history=history,  # type: ignore
            tool_defs=used_tool_defs,
        )

    @work
    async def action_rename_chat(self) -> None:
        store = await Store.get_store()

        screen = ChatRename(self.chat_name)
        new_name = await self.app.push_screen_wait(screen)
        if new_name is None:
            return
        tabs = self.app.query_one(TabbedContent)
        await store.rename_chat(self.db_id, new_name)
        tabs.get_tab(f"chat-{self.db_id}").update(new_name)

    async def action_regenerate_llm_message(self) -> None:
        if not self.messages[-1:]:
            return

        # Remove last Ollama response from UI and regenerate it
        response_message_id = self.messages[-1][0]
        self.messages.pop()
        message_container = self.query_one("#messageContainer")
        message_container.children[-1].remove()
        response_chat_item = ChatItem()
        response_chat_item.author = Author.OLLAMA
        message_container.mount(response_chat_item)
        loading = LoadingIndicator()
        await message_container.mount(loading)
        message_container.scroll_end()

        # Remove the last two messages from chat history, we will regenerate them
        self.ollama.history = self.ollama.history[:-2]
        message = self.messages[-1][2]

        async def response_task() -> None:
            response = ""
            async for text in self.ollama.stream(
                message,
                [img for _, img in self.images],
                Options(seed=random.randint(0, 32768)),
            ):
                response = text
                response_chat_item.text = text
                if message_container.can_view_partial(response_chat_item):
                    message_container.scroll_end()

            # Save to db
            store = await Store.get_store()
            await store.save_message(
                id=response_message_id,
                chat_id=self.db_id,
                author=Author.OLLAMA.value,
                text=response,
            )
            self.messages.append((response_message_id, Author.OLLAMA, response, []))
            self.images = []

            loading.remove()

        asyncio.create_task(response_task())

    async def action_history(self) -> None:
        def on_history_selected(text: str | None) -> None:
            if text is None:
                return
            prompt = self.query_one("#prompt", FlexibleInput)
            if "\n" in text and not prompt.is_multiline:
                prompt.toggle_multiline()
            prompt.text = text
            prompt.focus()

        prompts = [
            message for _, author, message, _ in self.messages if author == Author.USER
        ]
        prompts.reverse()
        screen = PromptHistory(prompts)
        self.app.push_screen(screen, on_history_selected)

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
