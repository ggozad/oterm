import asyncio
import base64
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from textual.app import App, ComposeResult
from textual.widgets import LoadingIndicator, Markdown

from oterm.app.widgets.chat import ChatContainer, ChatItem
from oterm.app.widgets.prompt import FlexibleInput
from oterm.types import ChatModel, MessageModel


class _Host(App):
    def __init__(self, chat_model: ChatModel, messages: list[MessageModel]):
        super().__init__()
        self._chat_model = chat_model
        self._messages = messages

    def compose(self) -> ComposeResult:
        yield ChatContainer(chat_model=self._chat_model, messages=self._messages)


def _notifications(app: App) -> list:
    return list(app._notifications)


class TestMount:
    async def test_renders_info_bar_with_model_name(self, chat_model):
        chat_model.model = "my-model"
        app = _Host(chat_model, [])
        async with app.run_test():
            from textual.widgets import Static

            info = app.query_one("#info", Static)
            assert "my-model" in str(info.render())

    async def test_prompt_is_focused_on_mount(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test():
            assert app.focused is not None
            assert app.focused.id == "promptInput"


class TestLoadMessages:
    async def test_mounts_chat_item_per_message(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        messages = [
            MessageModel(chat_id=chat_id, role="user", text="hi"),
            MessageModel(chat_id=chat_id, role="assistant", text="hello"),
        ]
        app = _Host(chat_model, messages)
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            await pilot.pause()

            items = list(container.query(ChatItem))
            assert len(items) == 2
            assert items[0].author == "user"
            assert items[1].author == "assistant"

    async def test_load_is_idempotent(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        messages = [MessageModel(chat_id=chat_id, role="user", text="hi")]
        app = _Host(chat_model, messages)
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            await container.load_messages()  # second call must not re-mount
            await pilot.pause()
            assert len(list(container.query(ChatItem))) == 1


class TestOnSubmit:
    async def test_empty_input_is_ignored(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = app.query_one(FlexibleInput)
            prompt.text = "   "
            await pilot.press("enter")
            await pilot.pause()
            assert container.messages == []

    async def test_submit_runs_response_task_and_saves_messages(
        self, store, chat_model
    ):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "hi "
            yield "there"

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            prompt = app.query_one(FlexibleInput)
            prompt.text = "hello"
            await pilot.press("enter")

            # Wait for the inference task to finish.
            for _ in range(50):
                await asyncio.sleep(0)
                await pilot.pause()
                if len(container.messages) == 2:
                    break

            assert container.messages[0].role == "user"
            assert container.messages[0].text == "hello"
            assert container.messages[1].role == "assistant"
            assert container.messages[1].text == "hi there"
            rows = await store.get_messages(chat_id)
            assert len(rows) == 2


class TestEscapeCancel:
    async def test_escape_cancels_running_inference(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        started = asyncio.Event()
        never = asyncio.Event()  # stays clear so the stream hangs

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            started.set()
            await never.wait()
            yield "unreachable"  # pragma: no cover

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            prompt = app.query_one(FlexibleInput)
            prompt.text = "slow"
            await pilot.press("enter")
            await started.wait()

            await pilot.press("escape")
            # Give the cancellation a chance to clean up mounted items.
            for _ in range(10):
                await asyncio.sleep(0)
                await pilot.pause()

            # Restored prompt text
            assert prompt.text == "slow"
            # No messages saved
            assert container.messages == []


class TestClearChat:
    async def test_clear_removes_messages_and_ui(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        msgs = [
            MessageModel(chat_id=chat_id, role="user", text="q"),
            MessageModel(chat_id=chat_id, role="assistant", text="a"),
        ]
        for m in msgs:
            m.id = await store.save_message(m)

        app = _Host(chat_model, msgs)
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            await pilot.pause()
            assert len(list(container.query(ChatItem))) == 2

            await container.action_clear_chat()
            await pilot.pause()

            assert container.messages == []
            assert container.pydantic_history == []
            assert list(container.query(ChatItem)) == []
            rows = await store.get_messages(chat_id)
            assert rows == []


class TestImages:
    async def test_image_added_appended_to_pending_images(self, chat_model):
        from oterm.app.widgets.image import ImageAdded

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.post_message(ImageAdded(Path("/tmp/a.png"), "base64data"))
            await pilot.pause()
            assert (Path("/tmp/a.png"), "base64data") in container.images

    async def test_malformed_image_is_skipped_with_notification(self, chat_model):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "ok "
            yield "response"

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            good = base64.b64encode(b"\x89PNG\r\n").decode()
            bad = "not-valid-base64!!"

            chunks = []
            async for chunk in container.stream_agent("look", images=[good, bad]):
                chunks.append(chunk)

            assert chunks[-1] == ("", "ok response")
            await pilot.pause()
            assert any("malformed" in n.message for n in _notifications(app))


class TestHistory:
    async def test_up_opens_history_modal(self, store, chat_model):
        from oterm.app.prompt_history import PromptHistory

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        msgs = [
            MessageModel(chat_id=chat_id, role="user", text="first"),
            MessageModel(chat_id=chat_id, role="assistant", text="answer"),
            MessageModel(chat_id=chat_id, role="user", text="second"),
        ]

        app = _Host(chat_model, msgs)
        async with app.run_test() as pilot:
            await pilot.press("up")
            await pilot.pause()
            assert isinstance(app.screen, PromptHistory)


class TestResponseTaskErrors:
    async def test_cannot_send_when_agent_is_none(self, app_config, chat_model):
        chat_model.provider = "openai-compat/ghost"
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            assert container.agent is None

            prompt = app.query_one(FlexibleInput)
            prompt.text = "hello"
            await pilot.press("enter")
            await pilot.pause()
            # Inference task should have notified immediately.
            for _ in range(10):
                await asyncio.sleep(0)
                await pilot.pause()
            assert any("Cannot send" in n.message for n in _notifications(app))
            assert container.messages == []

    async def test_stream_exception_notifies_and_cleans_up(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            raise RuntimeError("boom")
            yield  # pragma: no cover

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            prompt = app.query_one(FlexibleInput)
            prompt.text = "trigger"
            await pilot.press("enter")
            for _ in range(20):
                await asyncio.sleep(0)
                await pilot.pause()

            assert container.messages == []
            assert any("Unexpected error" in n.message for n in _notifications(app))
            # LoadingIndicator removed in finally block
            assert list(container.query(LoadingIndicator)) == []


class TestChatItemClickCopy:
    async def test_clicking_copies_text_to_clipboard(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            item.text = "the answer"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            copied: list[str] = []

            def fake_copy(text):
                copied.append(text)

            app.copy_to_clipboard = fake_copy  # ty: ignore[invalid-assignment]
            markdown = item.query_one(".response", Markdown)
            await pilot.click(markdown)
            await pilot.pause()
            assert copied == ["the answer"]
