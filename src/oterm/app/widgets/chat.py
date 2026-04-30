import asyncio
import base64
import binascii
import json
import time
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path
from typing import Any

import PIL.Image as PILImage
from PIL import UnidentifiedImageError
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
from pydantic_ai.messages import (
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    FilePart,
    FunctionToolResultEvent,
    ModelMessage,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.usage import RunUsage
from rich.console import Group, RenderableType
from rich.json import JSON
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Markdown,
    Static,
    TabbedContent,
)
from textual.widgets.markdown import MarkdownStream
from textual_image.widget import Image as TerminalImage

from oterm.agent import get_agent
from oterm.app.chat_edit import ChatEdit
from oterm.app.chat_rename import ChatRename
from oterm.app.prompt_history import PromptHistory
from oterm.app.widgets.image import ImageAdded
from oterm.app.widgets.prompt import IMAGE_TOKEN_RE, FlexibleInput, PostableTextArea
from oterm.store.store import Store
from oterm.tools import builtin_tools
from oterm.tools.mcp.setup import mcp_servers, mcp_tool_meta
from oterm.types import ChatModel, MessageModel

# Auto-follow the streaming response when the viewport is within this many
# rows of the bottom. Accounts for partial-row rounding and content shifts
# between check and scroll_end().
_SCROLL_FOLLOW_THRESHOLD = 2


def _near_bottom(container) -> bool:
    return container.max_scroll_y - container.scroll_y <= _SCROLL_FOLLOW_THRESHOLD


def _decode_image(b64: str) -> BinaryContent | None:
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError):
        return None
    return BinaryContent(data=data, media_type="image/png")


def build_user_prompt(
    text: str, images: list[str]
) -> tuple[str | list[str | BinaryContent], int]:
    """Interleave text and images by `[Image #N]` tokens, 1-indexed into images.

    Falls back to appending all images at the end when no tokens appear, so
    history saved before tokens existed still renders correctly on regenerate.
    Returns (user_prompt, skipped_count).
    """
    matches = list(IMAGE_TOKEN_RE.finditer(text))
    if not matches:
        if not images:
            return text, 0
        parts: list[str | BinaryContent] = [text] if text else []
        skipped = 0
        for b64 in images:
            content = _decode_image(b64)
            if content is None:
                skipped += 1
            else:
                parts.append(content)
        if not any(isinstance(p, BinaryContent) for p in parts):
            return text, skipped
        return parts, skipped

    parts = []
    last = 0
    skipped = 0
    for m in matches:
        if m.start() > last:
            parts.append(text[last : m.start()])
        idx = int(m.group(1))
        if 1 <= idx <= len(images):
            content = _decode_image(images[idx - 1])
            if content is None:
                skipped += 1
            else:
                parts.append(content)
        else:
            parts.append(m.group(0))
        last = m.end()
    if last < len(text):
        parts.append(text[last:])
    if not any(isinstance(p, BinaryContent) for p in parts):
        return text, skipped
    return parts, skipped


def _last_user_prompt_index(history: list[ModelMessage]) -> int | None:
    """Index of the most recent ModelRequest carrying a UserPromptPart.

    A "turn" in pydantic-ai history starts at a UserPromptPart and ends at
    the next assistant text response, but a tool-using turn fans out into
    request/response/request/response. Slicing a fixed -2 corrupts that.
    """
    for i in range(len(history) - 1, -1, -1):
        msg = history[i]
        if isinstance(msg, ModelRequest) and any(
            isinstance(p, UserPromptPart) for p in msg.parts
        ):
            return i
    return None


def _resolve_tools(tool_names: list[str]):
    """Split selected tool names into pydantic-ai Tool objects and filtered MCP toolsets."""
    from pydantic_ai import Tool as PydanticTool
    from pydantic_ai.toolsets import AbstractToolset

    from oterm.log import log

    selected = set(tool_names)
    tools: list[PydanticTool] = []
    available_names: set[str] = set()

    for tool_def in builtin_tools:
        available_names.add(tool_def["name"])
        if tool_def["name"] in selected:
            tools.append(tool_def["tool"])

    toolsets: list[AbstractToolset[None]] = []
    for server_name, meta in mcp_tool_meta.items():
        names_on_server = {m["name"] for m in meta}
        available_names |= names_on_server
        chosen = selected & names_on_server
        if chosen:
            toolsets.append(
                mcp_servers[server_name].filtered(
                    lambda _ctx, td, names=chosen: td.name in names
                )
            )

    missing = selected - available_names
    if missing:
        log.warning(f"Chat references unavailable tools: {sorted(missing)}")

    return tools, toolsets


class ChatContainer(Widget):
    messages: reactive[list[MessageModel]] = reactive([])
    images: list[tuple[Path, str]] = []

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
        self._stream_usage: RunUsage = RunUsage()

    def _rebuild_agent(self) -> None:
        """(Re)build the agent for the current chat_model. Defers errors to send time."""
        tools, toolsets = _resolve_tools(self.chat_model.tools)
        try:
            self.agent = get_agent(
                provider=self.chat_model.provider,
                model=self.chat_model.model,
                system=self.chat_model.system,
                tools=tools,
                toolsets=toolsets,
                parameters=self.chat_model.parameters,
                thinking=self.chat_model.thinking,
            )
            self._agent_error: str | None = None
        except Exception as e:
            self.agent = None
            self._agent_error = str(e)

    def _build_pydantic_history(
        self, messages: list[MessageModel]
    ) -> list[ModelMessage]:
        # Tool calls/responses from prior turns are not preserved across
        # reloads: the message schema only stores user/assistant text and
        # images, so a turn that fanned out into tool calls reconstructs as
        # a single TextPart of the final answer.
        pydantic_messages: list[ModelMessage] = []
        for msg_model in messages:
            if msg_model.role == "user":
                content, _ = build_user_prompt(msg_model.text, msg_model.images)
                pydantic_messages.append(
                    ModelRequest(parts=[UserPromptPart(content=content)])
                )
            else:
                pydantic_messages.append(
                    ModelResponse(parts=[TextPart(content=msg_model.text)])
                )
        return pydantic_messages

    def on_mount(self) -> None:
        self.query_one("#prompt").focus()

    async def stream_agent(
        self, user_prompt: str | list[str | BinaryContent]
    ) -> AsyncGenerator[
        TextPartDelta
        | ThinkingPartDelta
        | FilePart
        | ToolCallPart
        | BuiltinToolCallPart
        | ToolReturnPart
        | BuiltinToolReturnPart,
        Any,
    ]:
        if self.agent is None:
            raise RuntimeError(self._agent_error or "Agent is not configured")

        self._stream_usage = RunUsage()
        # Some providers (notably OpenAI Responses image_generation) emit the
        # same image twice — once as a partial-image event and once when the
        # call completes — under the same vendor part id. Dedupe by FilePart.id
        # so callers don't have to.
        seen_file_ids: set[str] = set()

        async with self.agent.iter(
            user_prompt, message_history=self.pydantic_history
        ) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for event in request_stream:
                            if isinstance(event, PartStartEvent):
                                if isinstance(event.part, ThinkingPart):
                                    if event.part.content:
                                        yield ThinkingPartDelta(
                                            content_delta=event.part.content
                                        )
                                elif isinstance(event.part, TextPart):
                                    if event.part.content:
                                        yield TextPartDelta(
                                            content_delta=event.part.content
                                        )
                                elif isinstance(event.part, FilePart):
                                    if event.part.id and event.part.id in seen_file_ids:
                                        continue
                                    if event.part.id:
                                        seen_file_ids.add(event.part.id)
                                    yield event.part
                                elif isinstance(
                                    event.part,
                                    (
                                        ToolCallPart,
                                        BuiltinToolCallPart,
                                        BuiltinToolReturnPart,
                                    ),
                                ):  # pragma: no branch
                                    yield event.part
                            elif isinstance(event, PartDeltaEvent):
                                if isinstance(
                                    event.delta, (TextPartDelta, ThinkingPartDelta)
                                ):  # pragma: no branch
                                    self._stream_usage = run.usage()
                                    yield event.delta
                elif Agent.is_call_tools_node(node):
                    async with node.stream(run.ctx) as tools_stream:
                        async for event in tools_stream:
                            if isinstance(
                                event, FunctionToolResultEvent
                            ) and isinstance(event.result, ToolReturnPart):
                                yield event.result
            if run.result is not None:  # pragma: no branch
                self.pydantic_history = list(run.result.all_messages())
                self._stream_usage = run.result.usage()

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
            if message.role == "assistant":
                for b64 in message.images:
                    decoded = _decode_image(b64)
                    if decoded is not None:  # pragma: no branch
                        await chat_item.add_image(decoded.data)
        self.loading = False
        self.loaded = True
        message_container.scroll_end()

    async def response_task(self, message: str) -> None:
        if self.agent is None:
            self.app.notify(
                f"Cannot send message: {self._agent_error}", severity="error"
            )
            return
        chat_id = self.chat_model.id
        assert chat_id is not None
        message_container = self.query_one("#messageContainer")

        user_chat_item = ChatItem()
        user_chat_item.author = "user"
        user_chat_item.text = message
        message_container.mount(user_chat_item)
        response_chat_item = ChatItem()
        response_chat_item.author = "assistant"
        message_container.mount(response_chat_item)
        status = UsageStatus()
        await message_container.mount(status)
        message_container.scroll_end()

        try:
            text = ""
            assistant_images: list[str] = []
            user_prompt, skipped = build_user_prompt(
                message, [img for _, img in self.images]
            )
            if skipped:
                self.app.notify(
                    f"Skipped {skipped} malformed image(s)", severity="warning"
                )
            async for piece in self.stream_agent(user_prompt):
                follow = _near_bottom(message_container)
                match piece:
                    case ThinkingPartDelta(content_delta=delta):
                        await response_chat_item.append_thinking(delta or "")
                    case TextPartDelta(content_delta=delta):
                        text += delta
                        await response_chat_item.append_text(delta)
                    case ToolCallPart() | BuiltinToolCallPart():
                        await response_chat_item.add_tool_call(piece)
                    case ToolReturnPart() | BuiltinToolReturnPart():
                        response_chat_item.update_tool_result(
                            piece.tool_call_id, piece.content
                        )
                    case FilePart(
                        content=BinaryContent(data=data)
                    ):  # pragma: no branch
                        await response_chat_item.add_image(data)
                        assistant_images.append(base64.b64encode(data).decode())
                status.update_usage(
                    self._stream_usage.input_tokens,
                    self._stream_usage.output_tokens,
                )
                if follow:  # pragma: no branch
                    message_container.scroll_end()

            await response_chat_item.finish_stream()

            status.update_usage(
                self._stream_usage.input_tokens,
                self._stream_usage.output_tokens,
            )
            status.finish()
            if _near_bottom(message_container):  # pragma: no branch
                self.call_after_refresh(message_container.scroll_end)

            store = await Store.get_store()

            user_message = MessageModel(
                id=None,
                chat_id=chat_id,
                role="user",
                text=message,
                images=[img for _, img in self.images],
            )
            id = await store.save_message(user_message)
            user_message.id = id
            self.messages.append(user_message)

            assistant_message = MessageModel(
                id=None,
                chat_id=chat_id,
                role="assistant",
                text=text,
                images=assistant_images,
            )
            id = await store.save_message(assistant_message)
            assistant_message.id = id
            self.messages.append(assistant_message)
            self.images = []

        except asyncio.CancelledError:
            response_chat_item.cancel_streams()
            user_chat_item.remove()
            response_chat_item.remove()
            status.remove()
            try:
                self.query_one("#prompt", FlexibleInput).text = message
            except NoMatches:  # pragma: no cover
                pass
            self.images = []
        except ModelHTTPError as e:
            response_chat_item.cancel_streams()
            user_chat_item.remove()
            response_chat_item.remove()
            status.remove()
            self.app.notify(
                f"There was an error running your request: {e}", severity="error"
            )
            message_container.scroll_end()
        except Exception as e:
            response_chat_item.cancel_streams()
            user_chat_item.remove()
            response_chat_item.remove()
            status.remove()
            self.app.notify(f"Unexpected error: {e}", severity="error")
            message_container.scroll_end()

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
        if hasattr(self, "inference_task"):  # pragma: no branch
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
        chat_id = self.chat_model.id
        assert chat_id is not None
        store = await Store.get_store()
        screen = ChatRename(self.chat_model.name)
        new_name = await self.app.push_screen_wait(screen)
        if new_name is None:
            return
        tabs = self.app.query_one(TabbedContent)
        await store.rename_chat(chat_id, new_name)
        tabs.get_tab(f"chat-{chat_id}").update(new_name)
        self.app.notify("Chat renamed")

    async def action_clear_chat(self) -> None:
        chat_id = self.chat_model.id
        assert chat_id is not None
        self.messages = []
        self.images = []
        self.pydantic_history = []

        self._rebuild_agent()
        msg_container = self.query_one("#messageContainer")
        for child in msg_container.children:
            child.remove()
        store = await Store.get_store()
        await store.clear_chat(chat_id)

    async def action_regenerate_llm_message(self) -> None:
        if self.agent is None:
            self.app.notify(f"Cannot regenerate: {self._agent_error}", severity="error")
            return
        if len(self.messages) < 2:
            return
        in_flight = getattr(self, "inference_task", None)
        if in_flight is not None and not in_flight.done():
            return  # pragma: no cover
        chat_id = self.chat_model.id
        assert chat_id is not None
        response_message_id = self.messages[-1].id
        popped_message = self.messages.pop()
        message_container = self.query_one("#messageContainer")
        message_container.children[-1].remove()
        response_chat_item = ChatItem()
        response_chat_item.author = "assistant"
        message_container.mount(response_chat_item)
        status = UsageStatus()
        await message_container.mount(status)
        message_container.scroll_end()

        turn_start = _last_user_prompt_index(self.pydantic_history) or 0
        popped_history = self.pydantic_history[turn_start:]
        self.pydantic_history = self.pydantic_history[:turn_start]
        message = self.messages[-1]

        def restore_state() -> None:
            self.messages.append(popped_message)
            self.pydantic_history = self.pydantic_history + popped_history
            response_chat_item.remove()
            status.remove()

        async def response_task() -> None:
            try:
                thinking = ""
                text = ""
                assistant_images: list[str] = []
                user_prompt, skipped = build_user_prompt(message.text, message.images)
                if skipped:
                    self.app.notify(
                        f"Skipped {skipped} malformed image(s)", severity="warning"
                    )
                async for piece in self.stream_agent(user_prompt):
                    follow = _near_bottom(message_container)
                    match piece:
                        case ThinkingPartDelta(content_delta=delta):
                            thinking += delta or ""
                            response_chat_item.thinking = thinking
                        case TextPartDelta(content_delta=delta):
                            text += delta or ""
                            response_chat_item.text = text
                        case ToolCallPart() | BuiltinToolCallPart():
                            await response_chat_item.add_tool_call(piece)
                        case ToolReturnPart() | BuiltinToolReturnPart():
                            response_chat_item.update_tool_result(
                                piece.tool_call_id, piece.content
                            )
                        case FilePart(  # pragma: no branch
                            content=BinaryContent(data=data)
                        ):
                            await response_chat_item.add_image(data)
                            assistant_images.append(base64.b64encode(data).decode())
                    status.update_usage(
                        self._stream_usage.input_tokens,
                        self._stream_usage.output_tokens,
                    )
                    if follow:  # pragma: no branch
                        message_container.scroll_end()

                status.update_usage(
                    self._stream_usage.input_tokens,
                    self._stream_usage.output_tokens,
                )
                status.finish()
                if _near_bottom(message_container):  # pragma: no branch
                    self.call_after_refresh(message_container.scroll_end)

                store = await Store.get_store()
                regenerated_message = MessageModel(
                    id=response_message_id,
                    chat_id=chat_id,
                    role="assistant",
                    text=text,
                    images=assistant_images,
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

        self.inference_task = asyncio.create_task(response_task())

    async def action_history(self) -> None:
        def on_history_selected(text: str | None) -> None:
            if text is None:
                return
            prompt = self.query_one("#prompt", FlexibleInput)
            prompt.text = text
            prompt.focus()

        prompts = [message.text for message in self.messages if message.role == "user"]
        prompts.reverse()
        screen = PromptHistory(prompts)
        self.app.push_screen(screen, on_history_selected)

    @on(ImageAdded)
    def on_image_added(self, ev: ImageAdded) -> None:
        self.images.append((ev.path, ev.image))
        token = f"[Image #{len(self.images)}] "
        try:
            textarea = self.query_one("#promptArea", PostableTextArea)
            textarea.insert(token)
            textarea.focus()
        except NoMatches:  # pragma: no cover
            pass
        self.app.notify(f"Image {ev.path} added.")

    def compose(self) -> ComposeResult:
        yield Static(f"model: {self.model}", id="info")
        yield VerticalScroll(id="messageContainer")
        yield FlexibleInput("", id="prompt")


_TOOL_TEXT_LIMIT = 1500
_NO_RESULT = object()


def _format_value(value: Any) -> RenderableType:
    """Type-aware rendering of a tool arg or result for the expanded body."""
    if isinstance(value, (dict, list)):
        return JSON.from_data(value, indent=2)
    if isinstance(value, str):
        try:
            return JSON.from_data(json.loads(value), indent=2)
        except (json.JSONDecodeError, ValueError, TypeError):
            return Text(_truncate(value, _TOOL_TEXT_LIMIT))
    if value is None:
        return Text("(none)", style="dim italic")
    return Text(_truncate(repr(value), _TOOL_TEXT_LIMIT))


def _format_field(label: str, value: Any) -> Group:
    return Group(
        Text(f"{label}:", style="bold cyan"),
        _format_value(value),
        Text(""),
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


class ToolCallItem(Widget):
    """Expandable marker for an assistant tool invocation.

    Header shows ``▸ tool call: <tool_name>`` (or ``▾`` when expanded). Body
    shows the args as type-aware Rich content and, once available, the result.
    """

    collapsed: reactive[bool] = reactive(True)

    def __init__(self, call: ToolCallPart | BuiltinToolCallPart, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.tool_name = call.tool_name
        self.tool_call_id = call.tool_call_id
        self.args: str | dict[str, Any] | None = call.args
        self.result: Any = _NO_RESULT

    def compose(self) -> ComposeResult:
        yield Static("", classes="tool-call-header")
        yield Static("", classes="tool-call-body")

    def on_mount(self) -> None:
        self._refresh()

    def set_result(self, content: Any) -> None:
        self.result = content
        self._refresh()

    async def on_click(self, event: Click) -> None:
        self.collapsed = not self.collapsed
        event.stop()

    def watch_collapsed(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        try:
            header = self.query_one(".tool-call-header", Static)
            body = self.query_one(".tool-call-body", Static)
        except NoMatches:  # pragma: no cover
            return
        arrow = "▸" if self.collapsed else "▾"
        header.update(f"{arrow} tool call: {self.tool_name}")
        if self.collapsed:
            body.display = False
            return
        fields = [_format_field("args", self.args)]
        if self.result is not _NO_RESULT:
            fields.append(_format_field("result", self.result))
        body.update(Group(*fields))
        body.display = True


class ChatItem(Widget):
    text: reactive[str] = reactive("")
    thinking: reactive[str] = reactive("")
    thoughts_collapsed: reactive[bool] = reactive(False)
    author: reactive[str] = reactive("")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._response_stream: MarkdownStream | None = None
        self._thinking_stream: MarkdownStream | None = None
        self._tool_calls: dict[str, ToolCallItem] = {}

    @on(Click)
    async def on_click(self, event: Click) -> None:
        cur: Widget | None = event.widget
        while cur is not None and cur is not self:
            if cur.has_class("thinking-label"):
                if self.thinking and self.text:
                    self.thoughts_collapsed = not self.thoughts_collapsed
                return
            if cur.has_class("thinking-body"):
                return
            cur = cur.parent  # ty: ignore[invalid-assignment]

        self.app.copy_to_clipboard(self.text)
        widgets = self.query(".text")
        for widget in widgets:
            widget.styles.animate("opacity", 0.5, duration=0.1)
            widget.styles.animate("opacity", 1.0, duration=0.1, delay=0.1)
        self.app.notify("Message copied to clipboard.")

    def _refresh_thinking_chrome(self) -> None:
        if self.author == "user":
            return
        try:
            label = self.query_one(".thinking-label", Static)
            body = self.query_one(".thinking-body", Markdown)
        except NoMatches:  # pragma: no cover
            return
        has_thinking = bool(self.thinking)
        label.display = has_thinking
        if not has_thinking:
            body.display = False
            return
        if not self.text:
            label.update("thinking…")
            body.display = True
        elif self.thoughts_collapsed:
            label.update("▸ thoughts")
            body.display = False
        else:
            label.update("▾ thoughts")
            body.display = True

    async def watch_text(self, text: str) -> None:
        if self.author == "user":
            return
        await self.query_one(".response", Markdown).update(text)
        if text and not self.thoughts_collapsed:
            self.thoughts_collapsed = True
        self._refresh_thinking_chrome()

    async def watch_thinking(self, thinking: str) -> None:
        if self.author == "user":
            return
        try:
            body = self.query_one(".thinking-body", Markdown)
        except NoMatches:  # pragma: no cover
            return
        await body.update(thinking)
        self._refresh_thinking_chrome()

    def watch_thoughts_collapsed(self) -> None:
        self._refresh_thinking_chrome()

    async def append_text(self, delta: str) -> None:
        """Stream a text delta into the response Markdown widget.

        Writes the delta via Textual's ``MarkdownStream`` (which batches and
        appends incrementally) instead of re-parsing the whole document each
        token through ``watch_text``. ``self.text`` is kept in sync via
        ``set_reactive`` so click-to-copy and chrome logic see live state
        without firing the watcher's full re-render.
        """
        if self.author == "user" or not delta:
            return
        if self._response_stream is None:
            try:
                response = self.query_one(".response", Markdown)
            except NoMatches:  # pragma: no cover
                return
            self._response_stream = Markdown.get_stream(response)
        self.set_reactive(ChatItem.text, self.text + delta)
        if not self.thoughts_collapsed:
            self.thoughts_collapsed = True
        await self._response_stream.write(delta)

    async def append_thinking(self, delta: str) -> None:
        """Stream a thinking delta into the thinking-body Markdown widget."""
        if self.author == "user" or not delta:
            return
        first_chunk = self._thinking_stream is None
        if self._thinking_stream is None:
            try:
                body = self.query_one(".thinking-body", Markdown)
            except NoMatches:  # pragma: no cover
                return
            self._thinking_stream = Markdown.get_stream(body)
        self.set_reactive(ChatItem.thinking, self.thinking + delta)
        if first_chunk:
            self._refresh_thinking_chrome()
        await self._thinking_stream.write(delta)

    async def add_tool_call(self, call: ToolCallPart | BuiltinToolCallPart) -> None:
        """Render an expandable tool-call marker before the response widget."""
        if self.author == "user":
            return
        try:
            response = self.query_one(".response", Markdown)
        except NoMatches:  # pragma: no cover
            return
        item = ToolCallItem(call)
        self._tool_calls[call.tool_call_id] = item
        await self.mount(item, before=response)

    def update_tool_result(self, tool_call_id: str, content: Any) -> None:
        """Attach a tool result to a previously rendered tool-call marker."""
        item = self._tool_calls.get(tool_call_id)
        if item is None:  # pragma: no cover
            return
        item.set_result(content)

    async def add_image(self, data: bytes) -> None:
        """Render an image emitted by the assistant before the response widget."""
        if self.author == "user":
            return
        try:
            response = self.query_one(".response", Markdown)
        except NoMatches:  # pragma: no cover
            return
        try:
            pil_image = PILImage.open(BytesIO(data))
        except UnidentifiedImageError:  # pragma: no cover
            return
        await self.mount(
            TerminalImage(pil_image, classes="assistantImage"), before=response
        )

    async def finish_stream(self) -> None:
        """Drain and stop any active streams started by ``append_*``."""
        if self._response_stream is not None:
            await self._response_stream.stop()
            self._response_stream = None
        if self._thinking_stream is not None:
            await self._thinking_stream.stop()
            self._thinking_stream = None

    def cancel_streams(self) -> None:
        """Cancel in-flight stream tasks without awaiting.

        Used in error/cancellation paths where the chat item is about to be
        removed; awaiting a graceful flush from inside an exception handler
        is unsafe. Reaches into ``MarkdownStream._task`` (Textual private API,
        verified against textual==8.2.4) because ``stream.stop()`` awaits.
        """
        for stream in (self._response_stream, self._thinking_stream):
            task = getattr(stream, "_task", None)
            if task is not None:
                task.cancel()
        self._response_stream = None
        self._thinking_stream = None

    def compose(self) -> ComposeResult:
        """A chat item."""

        if self.author == "user":
            with Horizontal(classes="user chatItem"):
                yield Static("❯", classes="prompt-marker")
                yield Static(self.text, markup=False, classes="text")
        else:
            with Horizontal(classes="assistant chatItem"):
                yield Static("❯", classes="prompt-marker")
                with Vertical(classes="response-column"):
                    yield Static("", classes="thinking-label")
                    yield Markdown(classes="thinking-body")
                    yield Markdown(classes="response")


class UsageStatus(Static):
    """Spinner-and-usage line shown below the active assistant response.

    While streaming, cycles a braille glyph and surfaces token counts and
    elapsed time as soon as the model reports them. After `finish()`, the
    glyph drops and the line stays in place as a dimmed footer for the turn.
    """

    SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    TICK_INTERVAL = 0.1

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("", **kwargs)
        self._frame = 0
        self._streaming = True
        self._input_tokens = 0
        self._output_tokens = 0
        self._started_at = time.monotonic()
        self._elapsed = 0.0
        self._timer: Any = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(self.TICK_INTERVAL, self._tick)
        self._refresh_text()

    def _tick(self) -> None:
        if self._streaming:  # pragma: no branch
            self._frame = (self._frame + 1) % len(self.SPINNER_FRAMES)
            self._elapsed = time.monotonic() - self._started_at
        self._refresh_text()

    def update_usage(self, input_tokens: int, output_tokens: int) -> None:
        if input_tokens == self._input_tokens and output_tokens == self._output_tokens:
            return
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._refresh_text()

    def finish(self) -> None:
        if not self._streaming:
            return
        self._streaming = False
        self._elapsed = time.monotonic() - self._started_at
        if self._timer is not None:  # pragma: no branch
            self._timer.stop()
            self._timer = None
        self._refresh_text()

    def _refresh_text(self) -> None:
        parts: list[str] = []
        if self._streaming:
            parts.append(self.SPINNER_FRAMES[self._frame])
        if self._input_tokens:
            parts.append(f"↑ {self._input_tokens}")
        if self._output_tokens:
            parts.append(f"↓ {self._output_tokens}")
        parts.append(f"{self._elapsed:.1f}s")
        self.update("  ".join(parts))
