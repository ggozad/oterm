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
    CSS_PATH = "../../src/oterm/app/oterm.tcss"

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
            assert app.focused.id == "promptArea"


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
    async def test_action_history_opens_modal(self, store, chat_model):
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
            container = app.query_one(ChatContainer)
            await container.action_history()
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


class TestEditChat:
    async def test_edit_chat_updates_model_and_agent(
        self, store, chat_model, monkeypatch
    ):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        from oterm.types import ChatModel

        updated_json = ChatModel(
            id=chat_id,
            name="renamed",
            model=chat_model.model,  # store.edit_chat doesn't update model
            system="be terse",
            provider="ollama",
            parameters={"temperature": 0.2},
            tools=[],
            thinking=True,
        ).model_dump_json()

        app = _Host(chat_model, [])

        async def fake_push_screen_wait(self, screen):
            return updated_json

        monkeypatch.setattr(type(app), "push_screen_wait", fake_push_screen_wait)

        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.action_edit_chat()
            for _ in range(20):
                await pilot.pause()
                if container.chat_model.system == "be terse":
                    break
            assert container.chat_model.system == "be terse"
            assert container.chat_model.thinking is True
            assert container.chat_model.parameters == {"temperature": 0.2}

            reloaded = await store.get_chat(chat_id)
            assert reloaded is not None
            assert reloaded.system == "be terse"
            assert reloaded.thinking is True
            assert reloaded.parameters == {"temperature": 0.2}

    async def test_edit_chat_cancelled_modal_is_noop(
        self, store, chat_model, monkeypatch
    ):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        app = _Host(chat_model, [])

        async def fake_push_screen_wait(self, screen):
            return None

        monkeypatch.setattr(type(app), "push_screen_wait", fake_push_screen_wait)

        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            original_model = container.chat_model.model
            container.action_edit_chat()
            for _ in range(5):
                await pilot.pause()
            assert container.chat_model.model == original_model


class TestRenameChat:
    async def test_rename_chat_updates_store_and_notifies(
        self, store, chat_model, monkeypatch
    ):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        from textual.widgets import TabbedContent, TabPane

        class _Host2(App):
            def __init__(self):
                super().__init__()

            def compose(self):
                with TabbedContent():
                    with TabPane("original", id=f"chat-{chat_id}"):
                        yield ChatContainer(chat_model=chat_model, messages=[])

        app = _Host2()

        async def fake_push_screen_wait(self, screen):
            return "new-name"

        monkeypatch.setattr(type(app), "push_screen_wait", fake_push_screen_wait)

        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.action_rename_chat()
            for _ in range(20):
                await pilot.pause()
                reloaded = await store.get_chat(chat_id)
                if reloaded and reloaded.name == "new-name":
                    break
            reloaded = await store.get_chat(chat_id)
            assert reloaded and reloaded.name == "new-name"
            assert any("renamed" in n.message for n in _notifications(app))

    async def test_rename_chat_cancelled_is_noop(self, store, chat_model, monkeypatch):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        chat_model.name = "unchanged"
        await store.edit_chat(chat_model)

        app = _Host(chat_model, [])

        async def fake_push_screen_wait(self, screen):
            return None

        monkeypatch.setattr(type(app), "push_screen_wait", fake_push_screen_wait)

        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.action_rename_chat()
            for _ in range(5):
                await pilot.pause()
            reloaded = await store.get_chat(chat_id)
            assert reloaded is not None
            assert reloaded.name == "unchanged"


class TestHistoryCallback:
    async def test_selecting_history_entry_fills_prompt(self, store, chat_model):
        from textual.widgets import OptionList

        from oterm.app.prompt_history import PromptHistory
        from oterm.app.widgets.prompt import FlexibleInput

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        msgs = [
            MessageModel(chat_id=chat_id, role="user", text="previous"),
            MessageModel(chat_id=chat_id, role="assistant", text="a"),
        ]
        app = _Host(chat_model, msgs)
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.action_history()
            await pilot.pause()
            assert isinstance(app.screen, PromptHistory)

            option_list = app.screen.query_one(OptionList)
            option_list.highlighted = 0
            await pilot.press("enter")
            await pilot.pause()

            prompt = container.query_one(FlexibleInput)
            assert prompt.text == "previous"

    async def test_cancelling_history_leaves_prompt_unchanged(self, store, chat_model):
        from oterm.app.widgets.prompt import FlexibleInput

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        msgs = [MessageModel(chat_id=chat_id, role="user", text="prev")]
        app = _Host(chat_model, msgs)
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.action_history()
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            prompt = container.query_one(FlexibleInput)
            assert prompt.text == ""

    async def test_selecting_history_populates_prompt(self, store, chat_model):
        from textual.widgets import OptionList

        from oterm.app.widgets.prompt import FlexibleInput

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        msgs = [MessageModel(chat_id=chat_id, role="user", text="line1\nline2")]
        app = _Host(chat_model, msgs)
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.action_history()
            await pilot.pause()

            option_list = app.screen.query_one(OptionList)
            option_list.highlighted = 0
            await pilot.press("enter")
            await pilot.pause()

            prompt = container.query_one(FlexibleInput)
            assert prompt.text == "line1\nline2"


class TestChatItemClickCopy:
    async def test_clicking_copies_text_to_clipboard(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test(size=(120, 40)) as pilot:
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


class TestChatItemUserAndJSON:
    async def test_user_chat_item_renders_with_static(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            item.text = "hello"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            from textual.widgets import Static

            statics = list(item.query(Static))
            assert any(s.has_class("text") for s in statics)
            # User items don't render a thinking label
            assert not list(item.query(".thinking-label"))

    async def test_assistant_json_text_rendered_as_code_block(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.text = '{"key": "value"}'
            await pilot.pause()
            # No assertion on Markdown internals — just that no exception raised
            markdown = item.query_one(".response", Markdown)
            assert markdown is not None

    async def test_setting_text_on_user_item_is_noop(self, chat_model):
        """watch_text short-circuits for user items since they render via Static."""
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.text = "hi"
            await pilot.pause()
            # No Markdown should be queried — and no exception raised.
            assert not list(item.query(Markdown))

    async def test_setting_thinking_on_user_item_is_noop(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.thinking = "hmm"  # should be swallowed without exception
            await pilot.pause()
