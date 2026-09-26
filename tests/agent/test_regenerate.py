import base64
import json
from collections.abc import AsyncIterator

from pydantic_ai import (
    Agent,
    ModelRequest,
    ModelResponse,
    TextPart,
    Tool,
    UserPromptPart,
)
from pydantic_ai.messages import (
    ModelMessage,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.function import (
    AgentInfo,
    DeltaThinkingPart,
    DeltaToolCall,
    FunctionModel,
)
from textual.app import App, ComposeResult

from oterm.app.widgets.chat import ChatContainer
from oterm.types import ChatModel, MessageModel
from tests._helpers import wait_until


class _Host(App):
    def __init__(self, chat_model: ChatModel, messages: list[MessageModel]):
        super().__init__()
        self._chat_model = chat_model
        self._messages = messages

    def compose(self) -> ComposeResult:
        yield ChatContainer(chat_model=self._chat_model, messages=self._messages)


def _notifications(app: App) -> list:
    return list(app._notifications)


class TestRegenerateGuards:
    async def test_no_op_with_fewer_than_two_messages(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        app = _Host(chat_model, [MessageModel(chat_id=chat_id, role="user", text="q")])
        async with app.run_test():
            container = app.query_one(ChatContainer)
            await container.action_regenerate_llm_message()
            assert len(container.messages) == 1

    async def test_notifies_when_agent_is_none(self, app_config):
        cm = ChatModel(model="m", provider="openai-compat/ghost")
        app = _Host(cm, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            assert container.agent is None
            await container.action_regenerate_llm_message()
            await wait_until(
                pilot,
                lambda: any(
                    "Cannot regenerate" in n.message for n in _notifications(app)
                ),
            )
            assert any("Cannot regenerate" in n.message for n in _notifications(app))


class TestRegenerateHappyPath:
    async def test_replaces_last_assistant_message(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="ask")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(
            chat_id=chat_id, role="assistant", text="old answer"
        )
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "new "
            yield "answer"

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "new answer")

            assert len(container.messages) == 2
            assert container.messages[-1].role == "assistant"
            assert container.messages[-1].text == "new answer"

            stored = await store.get_messages(chat_id)
            assistant_rows = [m for m in stored if m.role == "assistant"]
            assert len(assistant_rows) == 1
            assert assistant_rows[0].text == "new answer"

    async def test_thinking_streamed_into_chat_item(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="ask")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaThinkingPart]]:
            yield {0: DeltaThinkingPart(content="hmm")}
            yield "answer"

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "answer")
            assert container.messages[-1].text == "answer"

    async def test_file_part_streamed_through_regenerate(self, store, chat_model):
        from pydantic_ai.messages import BinaryImage, FilePart

        from tests._stream_helpers import make_file_aware_agent

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="ask")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | FilePart]:
            yield "redo "
            yield FilePart(
                content=BinaryImage(data=b"\x89PNG\r\n", media_type="image/png")
            )
            yield "answer"

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = make_file_aware_agent(stream_fn)

            await container.action_regenerate_llm_message()
            await wait_until(
                pilot, lambda: container.messages[-1].text == "redo answer"
            )
            assert container.messages[-1].text == "redo answer"

    async def test_tool_returning_binary_image_renders_and_persists(
        self, store, chat_model
    ):
        from pydantic_ai.messages import BinaryImage
        from textual_image.widget import Image as ImageWidget

        from oterm.app.widgets.chat import ChatItem
        from tests._helpers import image_b64

        png_bytes = base64.b64decode(image_b64())
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="draw")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        def make_image(prompt: str) -> BinaryImage:
            return BinaryImage(data=png_bytes, media_type="image/png")

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
            if any(
                isinstance(p, ToolReturnPart)
                for m in messages
                if isinstance(m, ModelRequest)
                for p in m.parts
            ):
                yield "done"
                return
            yield {
                0: DeltaToolCall(
                    name="make_image",
                    json_args='{"prompt": "a square"}',
                    tool_call_id="tc-img",
                )
            }

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(
                FunctionModel(stream_function=stream_fn),
                tools=[Tool(make_image, takes_ctx=False)],
            )

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "done")

            assistant = list(container.query(ChatItem))[-1]
            assert len(list(assistant.query(ImageWidget))) == 1
            assert container.messages[-1].images == [
                base64.b64encode(png_bytes).decode()
            ]
            stored = await store.get_messages(chat_id)
            assert stored[-1].images == container.messages[-1].images

    async def test_failing_tool_shows_error_in_call_widget(self, store, chat_model):
        from pydantic_ai.exceptions import ModelRetry

        from oterm.app.widgets.chat import ChatItem, ToolCallItem

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="go")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        def boom(s: str) -> str:
            raise ModelRetry("kaboom")

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
            if any(
                isinstance(p, RetryPromptPart)
                for m in messages
                if isinstance(m, ModelRequest)
                for p in m.parts
            ):
                yield "gave up"
                return
            yield {
                0: DeltaToolCall(
                    name="boom", json_args='{"s": "x"}', tool_call_id="tc-b"
                )
            }

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(
                FunctionModel(stream_function=stream_fn),
                tools=[Tool(boom, takes_ctx=False)],
            )

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "gave up")

            assistant = list(container.query(ChatItem))[-1]
            tool_items = list(assistant.query(ToolCallItem))
            assert len(tool_items) == 1
            assert isinstance(tool_items[0].result, str)
            assert tool_items[0].result.startswith("error:")
            assert "kaboom" in tool_items[0].result


class TestRegenerateErrorRestore:
    async def test_exception_restores_state_and_notifies(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="q")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            raise RuntimeError("boom")
            yield  # pragma: no cover

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await wait_until(
                pilot,
                lambda: any(
                    "Unexpected error" in n.message for n in _notifications(app)
                ),
            )

            assert container.messages[-1].text == "old"
            assert any("Unexpected error" in n.message for n in _notifications(app))

    async def test_model_http_error_restores_state_and_notifies(
        self, store, chat_model
    ):
        from pydantic_ai.exceptions import ModelHTTPError

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="q")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            raise ModelHTTPError(status_code=500, model_name="x", body="boom")
            yield  # pragma: no cover

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await wait_until(
                pilot,
                lambda: any(
                    "error running your request" in n.message
                    for n in _notifications(app)
                ),
            )

            assert container.messages[-1].text == "old"
            assert any(
                "error running your request" in n.message for n in _notifications(app)
            )


class TestLastUserPromptIndex:
    def test_empty_history_returns_none(self):
        from oterm.app.widgets.chat import _last_user_prompt_index

        assert _last_user_prompt_index([]) is None

    def test_finds_most_recent_user_prompt(self):
        from oterm.app.widgets.chat import _last_user_prompt_index

        history: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="first")]),
            ModelResponse(parts=[TextPart(content="a")]),
            ModelRequest(parts=[UserPromptPart(content="second")]),
            ModelResponse(parts=[TextPart(content="b")]),
        ]
        assert _last_user_prompt_index(history) == 2

    def test_skips_tool_return_requests(self):
        from oterm.app.widgets.chat import _last_user_prompt_index

        history: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="ask")]),
            ModelResponse(
                parts=[ToolCallPart(tool_name="t", args={}, tool_call_id="1")]
            ),
            ModelRequest(
                parts=[ToolReturnPart(tool_name="t", content="r", tool_call_id="1")]
            ),
        ]
        assert _last_user_prompt_index(history) == 0


def _count_user_prompts(history: list[ModelMessage]) -> int:
    return sum(
        1
        for msg in history
        if isinstance(msg, ModelRequest)
        and any(isinstance(p, UserPromptPart) for p in msg.parts)
    )


def _has_orphan_tool_call(history: list[ModelMessage]) -> bool:
    """Tool calls without a matching ToolReturnPart in a later request."""
    pending: set[str] = set()
    for msg in history:
        for part in msg.parts:
            if isinstance(part, ToolCallPart):
                pending.add(part.tool_call_id)
            elif isinstance(part, ToolReturnPart):
                pending.discard(part.tool_call_id)
    return bool(pending)


class TestRegenerateAfterToolUse:
    """Regenerate truncates the entire prior turn, including tool messages,
    so no orphan ToolCallParts remain in `pydantic_history`."""

    async def test_truncation_drops_full_tool_turn(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="ask")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(
            chat_id=chat_id, role="assistant", text="old answer"
        )
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[dict[int, DeltaToolCall] | str]:
            tool_returns_seen = sum(
                1
                for m in messages
                if isinstance(m, ModelRequest)
                and any(isinstance(p, ToolReturnPart) for p in m.parts)
            )
            if tool_returns_seen == 0:
                yield {
                    0: DeltaToolCall(name="ret_a", json_args=json.dumps({"x": "hi"}))
                }
            else:
                yield "regenerated "
                yield "answer"

        async def ret_a(x: str) -> str:
            return f"{x} world"

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()

            container.agent = Agent(
                FunctionModel(stream_function=stream_fn),
                tools=[Tool(ret_a, takes_ctx=False)],
            )
            # Seed pydantic_history as if the prior turn used a tool. This
            # mirrors `run.result.all_messages()` after a tool turn:
            # request(user) → response(tool_call) → request(tool_return) → response(text).
            container.pydantic_history = [
                ModelRequest(parts=[UserPromptPart(content="ask")]),
                ModelResponse(
                    parts=[
                        ToolCallPart(
                            tool_name="ret_a", args={"x": "hi"}, tool_call_id="t1"
                        )
                    ]
                ),
                ModelRequest(
                    parts=[
                        ToolReturnPart(
                            tool_name="ret_a", content="hi world", tool_call_id="t1"
                        )
                    ]
                ),
                ModelResponse(parts=[TextPart(content="old answer")]),
            ]

            await container.action_regenerate_llm_message()
            await wait_until(
                pilot, lambda: container.messages[-1].text == "regenerated answer"
            )

            # The new turn must keep history internally consistent: exactly one
            # UserPromptPart (the regenerated turn) and no orphan tool calls.
            assert _count_user_prompts(container.pydantic_history) == 1
            assert not _has_orphan_tool_call(container.pydantic_history)
            assert container.messages[-1].text == "regenerated answer"


class TestRegenerateAfterLiveSend:
    async def test_replaces_the_answer_sent_in_this_session(self, store, chat_model):
        from oterm.app.widgets.chat import ChatItem, UsageStatus
        from oterm.app.widgets.prompt import FlexibleInput

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        replies = iter(["first", "second"])

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield next(replies)

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            app.query_one(FlexibleInput).text = "ask"
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(container.messages) == 2)

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "second")
            await pilot.pause()

            answers = [
                i.text for i in container.query(ChatItem) if i.author == "assistant"
            ]
            assert answers == ["second"]
            assert len(container.query(UsageStatus)) == 1

    async def test_failed_regenerate_keeps_the_old_answer_on_screen(
        self, store, chat_model
    ):
        from oterm.app.widgets.chat import ChatItem

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="q")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            raise RuntimeError("boom")
            yield  # pragma: no cover

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await wait_until(
                pilot,
                lambda: any(
                    "Unexpected error" in n.message for n in _notifications(app)
                ),
            )
            await pilot.pause()

            answers = [
                i.text
                for i in container.query(ChatItem)
                if i.author == "assistant" and i.display
            ]
            assert answers == ["old"]

    async def test_keeps_images_attached_to_the_unsent_prompt(self, store, chat_model):
        from pathlib import Path

        from tests._helpers import image_b64

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="q")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "new"

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))
            draft = (Path("cat.png"), image_b64())
            container.images = [draft]

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "new")

            assert container.images == [draft]
