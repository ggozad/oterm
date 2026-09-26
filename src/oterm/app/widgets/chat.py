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
from pydantic_ai import Tool as PydanticTool
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    BinaryImage,
    FilePart,
    FunctionToolResultEvent,
    ModelMessage,
    NativeToolCallPart,
    NativeToolReturnPart,
    RetryPromptPart,
    SystemPromptPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset, PrefixedToolset
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
from oterm.config import envConfig
from oterm.log import log
from oterm.providers import openai_compat_context_window
from oterm.providers.capabilities import get_capabilities
from oterm.providers.ollama import running_context_length
from oterm.store.store import Store
from oterm.tools import builtin_tools, qualified_tool_name
from oterm.tools.capabilities import capability_defs
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
    try:
        fmt = PILImage.open(BytesIO(data)).format or "PNG"
    except UnidentifiedImageError:
        return None
    return BinaryContent(data=data, media_type=f"image/{fmt.lower()}")


def build_user_prompt(
    text: str, images: list[str]
) -> tuple[str | list[str | BinaryContent], int]:
    """Interleave text and images by `[Image #N]` tokens, 1-indexed into images.

    When the text has no tokens, all images follow the text; messages stored
    without tokens take this path. Returns (user_prompt, skipped_count).
    """
    parts: list[str | BinaryContent] = []
    skipped = 0

    def add_image(b64: str) -> None:
        nonlocal skipped
        content = _decode_image(b64)
        if content is None:
            skipped += 1
        else:
            parts.append(content)

    matches = list(IMAGE_TOKEN_RE.finditer(text))
    if matches:
        last = 0
        for m in matches:
            if m.start() > last:
                parts.append(text[last : m.start()])
            idx = int(m.group(1))
            if 1 <= idx <= len(images):
                add_image(images[idx - 1])
            else:
                parts.append(m.group(0))
            last = m.end()
        if last < len(text):
            parts.append(text[last:])
    else:
        if text:
            parts.append(text)
        for b64 in images:
            add_image(b64)

    if not any(isinstance(p, BinaryContent) for p in parts):
        return text, skipped
    return parts, skipped


def _last_user_prompt_index(history: list[ModelMessage]) -> int | None:
    """Index of the most recent ModelRequest carrying a UserPromptPart.

    A turn starts at a UserPromptPart, and a tool-using turn spans several
    request/response pairs, so its start is not at a fixed offset from the end.
    """
    for i in range(len(history) - 1, -1, -1):
        msg = history[i]
        if isinstance(msg, ModelRequest) and any(
            isinstance(p, UserPromptPart) for p in msg.parts
        ):
            return i
    return None


def _resolve_tools(tool_names: list[str]):
    """Split selected tool names into pydantic-ai Tool objects, filtered MCP toolsets and capabilities."""
    selected = set(tool_names)
    tools: list[PydanticTool] = []
    available_names: set[str] = set()

    for tool_def in builtin_tools:
        available_names.add(tool_def["name"])
        if tool_def["name"] in selected:
            tools.append(tool_def["tool"])

    capabilities: list[AbstractCapability[None]] = []
    for capability_def in capability_defs:
        available_names.add(capability_def["name"])
        if capability_def["name"] in selected:
            capabilities.append(capability_def["factory"]())

    toolsets: list[AbstractToolset[None]] = []
    for server_name, meta in mcp_tool_meta.items():
        by_qualified = {
            qualified_tool_name(server_name, m["name"]): m["name"] for m in meta
        }
        available_names |= by_qualified.keys()
        chosen = {by_qualified[q] for q in selected & by_qualified.keys()}
        if chosen:
            toolsets.append(
                PrefixedToolset(
                    mcp_servers[server_name].filtered(
                        lambda _ctx, td, names=chosen: td.name in names
                    ),
                    server_name,
                )
            )

    missing = selected - available_names
    if missing:
        log.warning(f"Chat references unavailable tools: {sorted(missing)}")

    return tools, toolsets, capabilities


def _error_message(error: Exception) -> str:
    if isinstance(error, ModelHTTPError):
        return f"There was an error running your request: {error}"
    return f"Unexpected error: {error}"


class ChatContainer(Widget):
    def __init__(
        self,
        *children: Widget,
        messages: list[MessageModel] | None = None,
        chat_model: ChatModel,
        **kwargs,
    ) -> None:
        super().__init__(*children, **kwargs)

        self.messages: list[MessageModel] = messages if messages is not None else []
        self.chat_model = chat_model

        self.pydantic_history: list[ModelMessage] = self._build_pydantic_history(
            self.messages
        )

        self._server_context_window: int | None = None
        self._rebuild_agent()
        self.loaded = False
        self.loading = False
        self.images: list[tuple[Path, str]] = []
        self.inference_task: asyncio.Task | None = None
        self._stream_usage: RunUsage = RunUsage()
        self._context_used = 0

    def _rebuild_agent(self) -> None:
        """(Re)build the agent for the current chat_model. Defers errors to send time."""
        tools, toolsets, capabilities = _resolve_tools(self.chat_model.tools)
        try:
            self.agent = get_agent(
                provider=self.chat_model.provider,
                model=self.chat_model.model,
                system=self.chat_model.system,
                tools=tools,
                toolsets=toolsets,
                capabilities=capabilities,
                parameters=self.chat_model.parameters,
                thinking=self.chat_model.thinking,
                context_window=self._server_context_window,
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
        | NativeToolCallPart
        | ToolReturnPart
        | NativeToolReturnPart
        | RetryPromptPart,
        Any,
    ]:
        if self.agent is None:
            raise RuntimeError(self._agent_error or "Agent is not configured")

        self._stream_usage = RunUsage()
        self._context_used = 0
        system_prompts_before = _system_prompts(self.pydantic_history)
        # Some providers (notably OpenAI Responses image_generation) emit the
        # same image twice under one vendor part id: as a partial-image event
        # and again when the call completes. Dedupe by FilePart.id.
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
                                        NativeToolCallPart,
                                        NativeToolReturnPart,
                                    ),
                                ):  # pragma: no branch
                                    yield event.part
                            elif isinstance(event, PartDeltaEvent):
                                if isinstance(
                                    event.delta, (TextPartDelta, ThinkingPartDelta)
                                ):  # pragma: no branch
                                    self._stream_usage = run.usage
                                    yield event.delta
                elif Agent.is_call_tools_node(node):
                    async with node.stream(run.ctx) as tools_stream:
                        async for event in tools_stream:
                            if not isinstance(event, FunctionToolResultEvent):
                                continue
                            if isinstance(event.part, ToolReturnPart):
                                yield event.part
                            elif isinstance(  # pragma: no branch
                                event.part, RetryPromptPart
                            ):
                                log.error(
                                    f"Tool {event.part.tool_name!r} failed: "
                                    f"{event.part.model_response()}"
                                )
                                yield event.part
            if run.result is not None:  # pragma: no branch
                self.pydantic_history = list(run.result.all_messages())
                self._stream_usage = run.result.usage
                self._context_used = run.result.response.usage.total_tokens
                # oterm sends its system prompt as instructions, so a new system
                # prompt in the history is a summary from the summarize capability.
                if _system_prompts(self.pydantic_history) - system_prompts_before:
                    self.app.notify(
                        "Older messages were summarized to fit the context window."
                    )

    async def _context_window(self) -> int | None:
        # Local servers report the context they actually run a model with,
        # which only exists once the model is loaded, so ask after each reply.
        provider, model = self.chat_model.provider, self.chat_model.model
        if provider == "ollama":
            return await asyncio.to_thread(running_context_length, model)
        if provider.startswith("openai-compat/"):
            endpoint = provider.removeprefix("openai-compat/")
            return await asyncio.to_thread(
                openai_compat_context_window, endpoint, model
            )
        # Agent resolves a model name into a Model when it is built.
        agent_model = self.agent.model if self.agent is not None else None
        assert isinstance(agent_model, Model)
        return agent_model.context_window

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

        def discard_turn() -> None:
            response_chat_item.cancel_streams()
            user_chat_item.remove()
            response_chat_item.remove()
            status.remove()

        try:
            user_images = [img for _, img in self.images]
            text, assistant_images = await self._stream_response(
                response_chat_item, status, message, user_images
            )

            store = await Store.get_store()
            user_message = MessageModel(
                chat_id=chat_id, role="user", text=message, images=user_images
            )
            user_message.id = await store.save_message(user_message)
            self.messages.append(user_message)

            assistant_message = MessageModel(
                chat_id=chat_id, role="assistant", text=text, images=assistant_images
            )
            assistant_message.id = await store.save_message(assistant_message)
            self.messages.append(assistant_message)
            self.images = []

        except asyncio.CancelledError:
            discard_turn()
            try:
                self.query_one("#prompt", FlexibleInput).text = message
            except NoMatches:  # pragma: no cover
                pass
            self.images = []
        except Exception as e:
            discard_turn()
            self.app.notify(_error_message(e), severity="error")
            message_container.scroll_end()

    async def _stream_response(
        self,
        item: "ChatItem",
        status: "UsageStatus",
        text: str,
        images: list[str],
    ) -> tuple[str, list[str]]:
        """Stream the agent's reply to `text` and `images` into `item`.

        Returns the reply text and the base64 images it produced.
        """
        message_container = self.query_one("#messageContainer")
        user_prompt, skipped = build_user_prompt(text, images)
        if skipped:
            self.app.notify(f"Skipped {skipped} malformed image(s)", severity="warning")

        reply = ""
        reply_images: list[str] = []
        async for piece in self.stream_agent(user_prompt):
            follow = _near_bottom(message_container)
            match piece:
                case ThinkingPartDelta(content_delta=delta):
                    await item.append_thinking(delta or "")
                case TextPartDelta(content_delta=delta):
                    reply += delta
                    await item.append_text(delta)
                case ToolCallPart() | NativeToolCallPart():
                    await item.add_tool_call(piece)
                case ToolReturnPart() | NativeToolReturnPart():
                    item.update_tool_result(piece.tool_call_id, piece.content)
                    contents = (
                        piece.content
                        if isinstance(piece.content, list)
                        else [piece.content]
                    )
                    for content in contents:
                        if isinstance(content, BinaryImage):
                            await item.add_image(content.data)
                            reply_images.append(base64.b64encode(content.data).decode())
                case RetryPromptPart():
                    item.update_tool_result(
                        piece.tool_call_id, f"error: {piece.model_response()}"
                    )
                case FilePart(content=BinaryImage(data=data)):
                    await item.add_image(data)
                    reply_images.append(base64.b64encode(data).decode())
            status.update_usage(
                self._stream_usage.input_tokens, self._stream_usage.output_tokens
            )
            if follow:  # pragma: no branch
                message_container.scroll_end()

        await item.finish_stream()
        status.update_usage(
            self._stream_usage.input_tokens, self._stream_usage.output_tokens
        )
        status.finish()
        if self._context_used:  # pragma: no branch
            self._show_context(status, self._context_used)
        if _near_bottom(message_container):  # pragma: no branch
            self.call_after_refresh(message_container.scroll_end)
        return reply, reply_images

    @work(group="context", exit_on_error=False)
    async def _show_context(self, status: "UsageStatus", used: int) -> None:
        """Add the context figure once the window is known, without holding up the turn."""
        window = await self._context_window()
        status.update_context(used, window)
        # Compaction reads the window from the model profile, and local
        # servers only report it once the model is loaded.
        if _is_local(self.chat_model.provider) and window not in (
            None,
            self._server_context_window,
        ):
            self._server_context_window = window
            self._rebuild_agent()

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
        if self.inference_task is not None:  # pragma: no branch
            self.inference_task.cancel()

    @work
    async def action_edit_chat(self) -> None:
        screen = ChatEdit(chat_model=self.chat_model, edit_mode=True)

        edited = await self.app.push_screen_wait(screen)
        if edited is None:
            return
        self.chat_model = edited

        store = await Store.get_store()
        await store.edit_chat(self.chat_model)

        self.pydantic_history = self._build_pydantic_history(self.messages)
        self._rebuild_agent()

    def action_toggle_thinking(self) -> None:
        """Toggle thinking for the current session only; not persisted."""
        if not get_capabilities(
            self.chat_model.provider, self.chat_model.model
        ).supports_thinking:
            self.app.notify(
                f"{self.chat_model.model} does not support thinking.",
                severity="warning",
            )
            return

        self.chat_model.thinking = not self.chat_model.thinking
        self._rebuild_agent()
        self.app.notify(f"Thinking {'on' if self.chat_model.thinking else 'off'}.")

    def action_copy_message(self) -> None:
        """Copy the last message. Reads the widget, not ``self.messages``, which
        is only appended once a response has finished streaming."""
        items = list(self.query_one("#messageContainer").query(ChatItem))
        if items:
            items[-1].copy()

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
        if self.inference_task is not None and not self.inference_task.done():
            return  # pragma: no cover
        chat_id = self.chat_model.id
        assert chat_id is not None
        response_message_id = self.messages[-1].id
        popped_message = self.messages.pop()
        message_container = self.query_one("#messageContainer")
        children = list(message_container.children)
        last_user = max(
            i
            for i, child in enumerate(children)
            if isinstance(child, ChatItem) and child.author == "user"
        )
        # The old answer and its usage line, hidden until the new answer lands.
        stale = children[last_user + 1 :]
        for widget in stale:
            widget.display = False
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
            response_chat_item.cancel_streams()
            response_chat_item.remove()
            status.remove()
            for widget in stale:
                widget.display = True

        async def response_task() -> None:
            try:
                text, images = await self._stream_response(
                    response_chat_item, status, message.text, message.images
                )
                store = await Store.get_store()
                regenerated_message = MessageModel(
                    id=response_message_id,
                    chat_id=chat_id,
                    role="assistant",
                    text=text,
                    images=images,
                )
                await store.save_message(regenerated_message)
                self.messages.append(regenerated_message)
                for widget in stale:
                    widget.remove()
            except asyncio.CancelledError:
                restore_state()
            except Exception as e:
                restore_state()
                self.app.notify(_error_message(e), severity="error")

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
        yield Static(f"model: {self.chat_model.model}", id="info")
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


class AssistantImage(
    TerminalImage,  # ty: ignore[unsupported-base]
    Renderable=TerminalImage._Renderable,
):
    """Inline image emitted by the assistant, retaining its source bytes so
    a click can later write them to disk."""

    def __init__(self, pil_image: PILImage.Image, data: bytes) -> None:
        super().__init__(pil_image, classes="assistantImage")
        self.image_bytes = data
        self.image_format = (pil_image.format or "PNG").lower()


class ToolCallItem(Widget):
    """Expandable marker for an assistant tool invocation.

    Header shows ``▸ tool call: <tool_name>`` (or ``▾`` when expanded). Body
    shows the args as type-aware Rich content and, once available, the result.
    """

    collapsed: reactive[bool] = reactive(True)

    def __init__(self, call: ToolCallPart | NativeToolCallPart, **kwargs: Any) -> None:
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
            if isinstance(cur, AssistantImage):
                await self._save_assistant_image(cur)
                return
            cur = cur.parent  # ty: ignore[invalid-assignment]

        self.copy()

    def copy(self) -> None:
        if not self.text:
            return
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

        Writes through Textual's ``MarkdownStream``, which batches deltas.
        ``self.text`` is updated with ``set_reactive`` so click-to-copy and the
        thinking chrome see the live text without ``watch_text`` re-rendering
        the whole document.
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

    async def add_tool_call(self, call: ToolCallPart | NativeToolCallPart) -> None:
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
        """Mount an assistant image above the response, keeping its source
        bytes so a click can save them to disk."""
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
        await self.mount(AssistantImage(pil_image, data), before=response)

    async def _save_assistant_image(self, image: AssistantImage) -> None:
        fmt = "jpg" if image.image_format == "jpeg" else image.image_format
        dest_dir = envConfig.OTERM_DATA_DIR / "downloads"
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"oterm-image-{int(time.time() * 1000)}.{fmt}"
        path.write_bytes(image.image_bytes)
        self.app.notify(f"Image saved to {path}")

    async def finish_stream(self) -> None:
        """Drain and stop any active streams started by ``append_*``.

        Per-delta ``Markdown.append`` advances the widget's internal
        ``_last_parsed_line`` to the start of the trailing top-level token,
        so an unclosed-then-closed code fence (or any partial block) can
        leave block state that drops content on the next refresh. Force a
        full ``Markdown.update`` with the accumulated text after stopping
        each stream to reset the widget to a clean re-parsed state.
        """
        if self._response_stream is not None:
            await self._response_stream.stop()
            self._response_stream = None
            try:
                response = self.query_one(".response", Markdown)
            except NoMatches:  # pragma: no cover
                pass
            else:
                await response.update(self.text)
        if self._thinking_stream is not None:
            await self._thinking_stream.stop()
            self._thinking_stream = None
            try:
                body = self.query_one(".thinking-body", Markdown)
            except NoMatches:  # pragma: no cover
                pass
            else:
                await body.update(self.thinking)

    def cancel_streams(self) -> None:
        """Cancel in-flight stream tasks without awaiting.

        Used in error/cancellation paths where the chat item is about to be
        removed; awaiting a graceful flush from inside an exception handler
        is unsafe. Reaches into ``MarkdownStream._task``, a Textual private
        attribute, because ``stream.stop()`` awaits.
        """
        for stream in (self._response_stream, self._thinking_stream):
            task = getattr(stream, "_task", None)
            if task is not None:
                task.cancel()
        self._response_stream = None
        self._thinking_stream = None

    def compose(self) -> ComposeResult:
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
        self._context_usage: tuple[int, int | None] | None = None
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

    def update_context(self, used: int, window: int | None) -> None:
        self._context_usage = (used, window)
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
        if self._context_usage is not None:
            used, window = self._context_usage
            if window:
                percent = round(100 * used / window)
                text = f"ctx {_compact(used)} / {_compact(window)} ({percent}%)"
                if percent >= 80:
                    text = f"[$error]{text}[/]"
                elif percent >= 50:
                    text = f"[$warning]{text}[/]"
                parts.append(text)
            else:
                parts.append(f"ctx {_compact(used)}")
        parts.append(f"{self._elapsed:.1f}s")
        self.update("  ".join(parts))


def _system_prompts(messages: list[ModelMessage]) -> set[str]:
    return {
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, SystemPromptPart)
    }


def _is_local(provider: str) -> bool:
    return provider == "ollama" or provider.startswith("openai-compat/")


def _compact(tokens: int) -> str:
    if tokens < 1000:
        return str(tokens)
    if tokens < 1_000_000:
        return f"{tokens / 1000:.1f}k"
    return f"{tokens / 1_000_000:.1f}M"
