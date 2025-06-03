import asyncio
import json
import random
from pathlib import Path

from ollama import Message, ResponseError
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
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
from oterm.app.mcp_prompt import MCPPrompt
from oterm.app.prompt_history import PromptHistory
from oterm.app.widgets.image import ImageAdded
from oterm.app.widgets.prompt import FlexibleInput
from oterm.ollamaclient import OllamaLLM, Options
from oterm.store.store import Store
from oterm.tools import available_tool_calls
from oterm.types import ChatModel, MessageModel
from oterm.utils import parse_response


class ChatContainer(Widget):
    ollama = OllamaLLM()
    messages: reactive[list[MessageModel]] = reactive([])
    images: list[tuple[Path, str]] = []
    BINDINGS = [
        Binding("up", "history", "history"),
        Binding(
            "escape", "cancel_inference", "cancel inference", show=False, priority=True
        ),
    ]

    def __init__(
        self,
        *children: Widget,
        messages: list[MessageModel] = [],
        chat_model: ChatModel,
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)

        self.messages = messages
        self.chat_model = chat_model
        history = []
        # This is wrong, the images should be a list of Image objects
        # See https://github.com/ollama/ollama-python/issues/375
        # Temp fix is to do msg.images = images  # type: ignore
        for msg_model in messages:
            message_text = msg_model.text
            msg = Message(
                role=msg_model.role,
                content=(
                    message_text
                    if msg_model.role == "user"
                    else parse_response(message_text).response
                ),
            )
            msg.images = msg_model.images  # type: ignore
            history.append(msg)

        used_tool_defs = [
            tool_def
            for tool_def in available_tool_calls()
            if tool_def["tool"] in chat_model.tools
        ]

        self.ollama = OllamaLLM(
            model=chat_model.model,
            system=chat_model.system,
            format=chat_model.format,
            options=chat_model.parameters,
            keep_alive=chat_model.keep_alive,
            history=history,
            tool_defs=used_tool_defs,
            thinking=chat_model.thinking,
        )
        self.loaded = False
        self.loading = False
        self.images = []

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()

    async def load_messages(self) -> None:
        if self.loaded or self.loading:
            return
        self.loading = True
        message_container = self.query_one("#messageContainer")
        for message in self.messages:
            chat_item = ChatItem()
            chat_item.text = (
                message.text
                if message.role == "user"
                else parse_response(message.text).formatted_output
            )
            chat_item.author = message.role
            await message_container.mount(chat_item)
        message_container.scroll_end()
        self.loading = False
        self.loaded = True

    async def response_task(self, message: str) -> None:
        message_container = self.query_one("#messageContainer")

        user_chat_item = ChatItem()
        user_chat_item.text = message
        user_chat_item.author = "user"
        message_container.mount(user_chat_item)

        response_chat_item = ChatItem()
        response_chat_item.author = "assistant"
        message_container.mount(response_chat_item)
        loading = LoadingIndicator()
        await message_container.mount(loading)
        message_container.scroll_end()

        try:
            response = ""

            async for thought, text in self.ollama.stream(
                message, [img for _, img in self.images]
            ):
                response = f"<think>{thought}</think>{text}"
                response_chat_item.text = parse_response(response).formatted_output

            parsed = parse_response(response)

            # To not exhaust the tokens, remove the thought process from the history (it seems to be the common practice)
            self.ollama.history[-1].content = parsed.response  # type: ignore
            response_chat_item.text = parsed.formatted_output

            if message_container.can_view_partial(response_chat_item):
                message_container.scroll_end()

            store = await Store.get_store()

            # Create and save user message model
            user_message = MessageModel(
                id=None,
                chat_id=self.chat_model.id,  # type: ignore
                role="user",
                text=message,
                images=[img for _, img in self.images],
            )
            id = await store.save_message(user_message)
            user_message.id = id
            self.messages.append(user_message)

            # Create and save assistant message model
            assistant_message = MessageModel(
                id=None,
                chat_id=self.chat_model.id,  # type: ignore
                role="assistant",
                text=parsed.response,
                images=[],
            )
            id = await store.save_message(assistant_message)
            assistant_message.id = id
            self.messages.append(assistant_message)
            self.images = []

        except asyncio.CancelledError:
            user_chat_item.remove()
            response_chat_item.remove()
            input = self.query_one("#prompt", FlexibleInput)
            input.text = message
        except ResponseError as e:
            user_chat_item.remove()
            response_chat_item.remove()
            self.app.notify(
                f"There was an error running your request: {e}", severity="error"
            )
            message_container.scroll_end()

        finally:
            loading.remove()

    @on(FlexibleInput.Submitted)
    async def on_submit(self, event: FlexibleInput.Submitted) -> None:
        message = event.value
        input = event.input

        input.clear()
        if not message.strip():
            input.focus()
            return

        self.inference_task = asyncio.create_task(self.response_task(message))

    def key_escape(self) -> None:
        if hasattr(self, "inference_task"):
            self.inference_task.cancel()

    @work
    async def action_edit_chat(self) -> None:
        screen = ChatEdit(chat_model=self.chat_model, edit_mode=True)

        model_info = await self.app.push_screen_wait(screen)
        if model_info is None:
            return

        self.chat_model = ChatModel.model_validate_json(model_info)

        # Save to database
        store = await Store.get_store()
        await store.edit_chat(self.chat_model)

        # load the history from messages
        history: list[Message] = []
        # This is wrong, the images should be a list of Image objects
        # See https://github.com/ollama/ollama-python/issues/375
        # Temp fix is to do msg.images = images  # type: ignore
        for message in self.messages:
            msg = Message(
                role=message.role,
                content=message.text,
            )
            msg.images = message.images  # type: ignore
            history.append(msg)

        # Get tool definitions based on the updated tools list
        used_tool_defs = [
            tool_def
            for tool_def in available_tool_calls()
            if tool_def["tool"] in self.chat_model.tools
        ]

        # Recreate the Ollama client with updated parameters
        self.ollama = OllamaLLM(
            model=self.chat_model.model,
            system=self.chat_model.system,
            format=self.chat_model.format,
            options=self.chat_model.parameters,
            keep_alive=self.chat_model.keep_alive,
            history=history,  # type: ignore
            tool_defs=used_tool_defs,
            thinking=self.chat_model.thinking,
        )

    @work
    async def action_rename_chat(self) -> None:
        store = await Store.get_store()
        screen = ChatRename(self.chat_model.name)
        new_name = await self.app.push_screen_wait(screen)
        if new_name is None:
            return
        tabs = self.app.query_one(TabbedContent)
        await store.rename_chat(self.chat_model.id, new_name)  # type: ignore
        tabs.get_tab(f"chat-{self.chat_model.id}").update(new_name)
        self.app.notify("Chat renamed")

    async def action_clear_chat(self) -> None:
        self.messages = []
        self.images = []
        self.ollama = OllamaLLM(
            model=self.ollama.model,
            system=self.ollama.system,
            format=self.ollama.format,  # type: ignore
            options=self.chat_model.parameters,
            keep_alive=self.ollama.keep_alive,
            history=[],  # type: ignore
            tool_defs=self.ollama.tool_defs,
            thinking=self.chat_model.thinking,
        )
        msg_container = self.query_one("#messageContainer")
        for child in msg_container.children:
            child.remove()
        store = await Store.get_store()
        await store.clear_chat(self.chat_model.id)  # type: ignore

    async def action_regenerate_llm_message(self) -> None:
        if not self.messages[-1:]:
            return
        # Remove last Ollama response from UI and regenerate it
        response_message_id = self.messages[-1].id
        self.messages.pop()
        message_container = self.query_one("#messageContainer")
        message_container.children[-1].remove()
        response_chat_item = ChatItem()
        response_chat_item.author = "assistant"
        message_container.mount(response_chat_item)
        loading = LoadingIndicator()
        await message_container.mount(loading)
        message_container.scroll_end()

        # Remove the last two messages from chat history, we will regenerate them
        self.ollama.history = self.ollama.history[:-2]
        message = self.messages[-1]

        async def response_task() -> None:
            response = await self.ollama.completion(
                message.text,
                images=message.images,  # type: ignore
                additional_options=Options(seed=random.randint(0, 32768)),
            )
            response_chat_item.text = response
            if message_container.can_view_partial(response_chat_item):
                message_container.scroll_end()

            # Save to db
            store = await Store.get_store()

            # Create a message model for regenerated response
            regenerated_message = MessageModel(
                id=response_message_id,
                chat_id=self.chat_model.id,  # type: ignore
                role="assistant",
                text=response,
                images=[],
            )
            await store.save_message(regenerated_message)
            regenerated_message.id = response_message_id
            self.messages.append(regenerated_message)
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

        prompts = [message.text for message in self.messages if message.role == "user"]
        prompts.reverse()
        screen = PromptHistory(prompts)
        self.app.push_screen(screen, on_history_selected)

    @work
    async def action_mcp_prompt(self) -> None:
        screen = MCPPrompt()
        messages = await self.app.push_screen_wait(screen)
        if messages is None:
            return
        messages = [Message(**msg) for msg in json.loads(messages)]
        message_container = self.query_one("#messageContainer")
        store = await Store.get_store()

        last_user_message = None
        if messages[-1].role == "user":
            last_user_message = messages.pop()

        for message in messages:
            text = message.content or ""
            # Create a message model for the MCP conversation
            message_model = MessageModel(
                id=None,
                chat_id=self.chat_model.id,  # type: ignore
                role=message.role,  # type: ignore
                text=text,
                images=[],
            )
            id = await store.save_message(message_model)
            message_model.id = id
            self.messages.append(message_model)
            chat_item = ChatItem()
            chat_item.text = text
            chat_item.author = message.role
            await message_container.mount(chat_item)
        message_container.scroll_end()
        if last_user_message is not None and last_user_message.content:
            await self.response_task(last_user_message.content)

    @on(ImageAdded)
    def on_image_added(self, ev: ImageAdded) -> None:
        self.images.append((ev.path, ev.image))
        self.app.notify(f"Image {ev.path} added.")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"model: {self.ollama.model}", id="info")
            yield VerticalScroll(
                id="messageContainer",
            )
            yield FlexibleInput("", id="prompt", classes="singleline")


class ChatItem(Widget):
    text: reactive[str] = reactive("")
    author: reactive[str] = reactive("")

    @on(Click)
    async def on_click(self, event: Click) -> None:
        self.app.copy_to_clipboard(self.text)
        widgets = self.query(".text")
        for widget in widgets:
            widget.styles.animate("opacity", 0.5, duration=0.1)
            widget.styles.animate("opacity", 1.0, duration=0.1, delay=0.1)
        self.app.notify("Message copied to clipboard.")

    async def watch_text(self, text: str) -> None:
        if self.author == "user":
            return
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
        with Horizontal(classes=f"{self.author} chatItem"):
            if self.author == "user":
                yield Static(self.text, classes="text")
            else:
                yield mrk_down
