import asyncio
import base64
import binascii
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic_ai import (
    Agent,
    BinaryContent,
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPartDelta,
    UserPromptPart,
)
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ThinkingPart
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

from oterm.agent import get_agent
from oterm.app.chat_edit import ChatEdit
from oterm.app.chat_rename import ChatRename
from oterm.app.mcp_prompt import MCPPrompt
from oterm.app.prompt_history import PromptHistory
from oterm.app.widgets.image import ImageAdded
from oterm.app.widgets.prompt import FlexibleInput
from oterm.store.store import Store
from oterm.tools import available_tools
from oterm.types import ChatModel, MessageModel


def _resolve_tools(tool_names: list[str]):
    from pydantic_ai import Tool as PydanticTool

    from oterm.log import log

    tools: list[PydanticTool] = []
    available_names: set[str] = set()
    for tool_def in available_tools():
        available_names.add(tool_def["name"])
        if tool_def["name"] in tool_names:
            tools.append(tool_def["tool"])
    missing = set(tool_names) - available_names
    if missing:
        log.warning(f"Chat references unavailable tools: {sorted(missing)}")
    return tools


class ChatContainer(Widget):
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
        self.model = chat_model.model
        self.system = chat_model.system

        self.pydantic_history: list[ModelMessage] = self._build_pydantic_history(
            messages
        )

        self._rebuild_agent()
        self.loaded = False
        self.loading = False
        self.images = []

    def _rebuild_agent(self) -> None:
        """(Re)build the agent for the current chat_model. Defers errors to send time."""
        tools = _resolve_tools(self.chat_model.tools)
        try:
            self.agent = get_agent(
                provider=self.chat_model.provider,
                model=self.chat_model.model,
                system=self.chat_model.system,
                tools=tools,
                parameters=self.chat_model.parameters,
                thinking=self.chat_model.thinking,
            )
            self._agent_error: str | None = None
        except Exception as e:
            self.agent = None  # type: ignore[assignment]
            self._agent_error = str(e)

    def _build_pydantic_history(
        self, messages: list[MessageModel]
    ) -> list[ModelMessage]:
        pydantic_messages: list[ModelMessage] = []
        for msg_model in messages:
            if msg_model.role == "user":
                pydantic_messages.append(
                    ModelRequest(parts=[UserPromptPart(content=msg_model.text)])
                )
            elif msg_model.role == "assistant":
                pydantic_messages.append(
                    ModelResponse(parts=[TextPart(content=msg_model.text)])
                )
        return pydantic_messages

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()

    async def stream_agent(
        self, prompt: str, images: list[str] = []
    ) -> AsyncGenerator[tuple[str, str], Any]:
        if self.agent is None:
            raise RuntimeError(self._agent_error or "Agent is not configured")
        user_prompt: str | list[str | BinaryContent]
        if images:
            user_prompt = [prompt]
            skipped = 0
            for img_base64 in images:
                try:
                    img_bytes = base64.b64decode(img_base64, validate=True)
                except (binascii.Error, ValueError):
                    skipped += 1
                    continue
                user_prompt.append(
                    BinaryContent(data=img_bytes, media_type="image/png")  # type: ignore[reportCallIssue]
                )
            if skipped:
                self.app.notify(
                    f"Skipped {skipped} malformed image(s)", severity="warning"
                )
        else:
            user_prompt = prompt

        thinking = ""
        text = ""

        async with self.agent.iter(
            user_prompt, message_history=self.pydantic_history
        ) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if isinstance(event, PartStartEvent):
                                if isinstance(event.part, ThinkingPart):
                                    thinking += event.part.content or ""
                                elif isinstance(event.part, TextPart):
                                    text += event.part.content or ""
                            elif isinstance(event, PartDeltaEvent):
                                if isinstance(event.delta, ThinkingPartDelta):
                                    thinking += event.delta.content_delta or ""
                                elif isinstance(event.delta, TextPartDelta):
                                    text += event.delta.content_delta or ""
                                yield thinking, text
            if run.result is not None:
                self.pydantic_history = list(run.result.all_messages())

    async def load_messages(self) -> None:
        message_container = self.query_one("#messageContainer")
        if self.loaded or self.loading:
            message_container.scroll_end()
            return
        self.loading = True
        for message in self.messages:
            chat_item = ChatItem()
            chat_item.author = message.role
            chat_item.text = message.text
            await message_container.mount(chat_item)
        self.loading = False
        self.loaded = True
        message_container.scroll_end()

    async def response_task(self, message: str) -> None:
        if self.agent is None:
            self.app.notify(
                f"Cannot send message: {self._agent_error}", severity="error"
            )
            return
        message_container = self.query_one("#messageContainer")

        user_chat_item = ChatItem()
        user_chat_item.author = "user"
        user_chat_item.text = message
        message_container.mount(user_chat_item)
        response_chat_item = ChatItem()
        response_chat_item.author = "assistant"
        message_container.mount(response_chat_item)
        loading = LoadingIndicator()
        await message_container.mount(loading)
        message_container.scroll_end()

        try:
            thinking = ""
            text = ""

            async for thinking, text in self.stream_agent(
                message, [img for _, img in self.images]
            ):
                response_chat_item.thinking = thinking
                response_chat_item.text = text

            if message_container.can_view_partial(response_chat_item):
                message_container.scroll_end()

            store = await Store.get_store()

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

            assistant_message = MessageModel(
                id=None,
                chat_id=self.chat_model.id,  # type: ignore
                role="assistant",
                text=text,
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
        except ModelHTTPError as e:
            user_chat_item.remove()
            response_chat_item.remove()
            self.app.notify(
                f"There was an error running your request: {e}", severity="error"
            )
            message_container.scroll_end()
        except Exception as e:
            user_chat_item.remove()
            response_chat_item.remove()
            self.app.notify(f"Unexpected error: {e}", severity="error")
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

        store = await Store.get_store()
        await store.edit_chat(self.chat_model)

        self.pydantic_history = self._build_pydantic_history(self.messages)

        self.model = self.chat_model.model
        self.system = self.chat_model.system

        self._rebuild_agent()

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
        self.pydantic_history = []

        self._rebuild_agent()
        msg_container = self.query_one("#messageContainer")
        for child in msg_container.children:
            child.remove()
        store = await Store.get_store()
        await store.clear_chat(self.chat_model.id)  # type: ignore

    async def action_regenerate_llm_message(self) -> None:
        if self.agent is None:
            self.app.notify(f"Cannot regenerate: {self._agent_error}", severity="error")
            return
        if len(self.messages) < 2:
            return
        response_message_id = self.messages[-1].id
        popped_message = self.messages.pop()
        message_container = self.query_one("#messageContainer")
        message_container.children[-1].remove()
        response_chat_item = ChatItem()
        response_chat_item.author = "assistant"
        message_container.mount(response_chat_item)
        loading = LoadingIndicator()
        await message_container.mount(loading)
        message_container.scroll_end()

        # Remove the last request+response pair from pydantic history
        popped_history = self.pydantic_history[-2:]
        if len(self.pydantic_history) >= 2:
            self.pydantic_history = self.pydantic_history[:-2]
        message = self.messages[-1]

        def restore_state() -> None:
            self.messages.append(popped_message)
            self.pydantic_history = self.pydantic_history + popped_history
            response_chat_item.remove()

        async def response_task() -> None:
            try:
                thinking = ""
                text = ""
                async for thinking, text in self.stream_agent(
                    message.text,
                    images=message.images,
                ):
                    response_chat_item.thinking = thinking
                    response_chat_item.text = text
                    if message_container.can_view_partial(response_chat_item):
                        message_container.scroll_end()

                if not text:
                    restore_state()
                    self.app.notify("No response received", severity="error")
                    return

                store = await Store.get_store()
                regenerated_message = MessageModel(
                    id=response_message_id,
                    chat_id=self.chat_model.id,  # type: ignore
                    role="assistant",
                    text=text,
                    images=[],
                )
                await store.save_message(regenerated_message)
                regenerated_message.id = response_message_id
                self.messages.append(regenerated_message)
                self.images = []

            except asyncio.CancelledError:
                restore_state()
            except ModelHTTPError as e:
                restore_state()
                self.app.notify(
                    f"There was an error running your request: {e}", severity="error"
                )
            except Exception as e:
                restore_state()
                self.app.notify(f"Unexpected error: {e}", severity="error")
            finally:
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
        parsed_messages = json.loads(messages)
        message_container = self.query_one("#messageContainer")
        store = await Store.get_store()

        last_user_message = None
        if parsed_messages[-1]["role"] == "user":
            last_user_message = parsed_messages.pop()

        for msg in parsed_messages:
            text = msg.get("content", "")
            message_model = MessageModel(
                id=None,
                chat_id=self.chat_model.id,  # type: ignore
                role=msg["role"],
                text=text,
                images=[],
            )
            id = await store.save_message(message_model)
            message_model.id = id
            self.messages.append(message_model)
            chat_item = ChatItem()
            chat_item.text = text
            chat_item.author = msg["role"]
            await message_container.mount(chat_item)
        message_container.scroll_end()
        if last_user_message is not None and last_user_message.get("content"):
            await self.response_task(last_user_message["content"])

    @on(ImageAdded)
    def on_image_added(self, ev: ImageAdded) -> None:
        self.images.append((ev.path, ev.image))
        self.app.notify(f"Image {ev.path} added.")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"model: {self.model}", id="info")
            yield VerticalScroll(
                id="messageContainer",
            )
            yield FlexibleInput("", id="prompt", classes="singleline")


class ChatItem(Widget):
    text: reactive[str] = reactive("")
    thinking: reactive[str] = reactive("")
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

        txt_widget = self.query_one(".response", Markdown)
        await txt_widget.update(text)

    async def watch_thinking(self, thinking: str) -> None:
        if self.author == "user":
            return
        try:
            label = self.query_one(".thinking-label")
            body = self.query_one(".thinking-body", Markdown)
        except Exception:
            return
        has_thinking = bool(thinking)
        label.display = has_thinking
        body.display = has_thinking
        await body.update(thinking)

    def compose(self) -> ComposeResult:
        """A chat item."""

        with Horizontal(classes=f"{self.author} chatItem"):
            if self.author == "user":
                yield Static(self.text, markup=False, classes="text")
            else:
                with Vertical(classes="text"):
                    yield Static("🤔 thinking", classes="thinking-label")
                    yield Markdown(classes="thinking-body")
                    yield Markdown(classes="response")
