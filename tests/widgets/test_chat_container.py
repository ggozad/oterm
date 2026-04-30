import asyncio
import base64
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, TextPartDelta
from pydantic_ai.models.function import AgentInfo, FunctionModel
from rich.console import Console
from rich.json import JSON
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Markdown

from oterm.app.widgets.chat import (
    ChatContainer,
    ChatItem,
    ToolCallItem,
    UsageStatus,
    _format_value,
    _truncate,
)
from oterm.app.widgets.prompt import FlexibleInput
from oterm.types import ChatModel, MessageModel
from tests._helpers import wait_until


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

            await wait_until(pilot, lambda: len(container.messages) == 2)

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
    async def test_image_added_appended_and_token_inserted_at_cursor(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            textarea.text = "before after"
            textarea.cursor_location = (0, 7)  # between "before " and "after"
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "base64data"))
            await pilot.pause()

            assert (Path("/tmp/a.png"), "base64data") in container.images
            assert textarea.text == "before [Image #1] after"

    async def test_second_image_gets_next_index(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "data1"))
            await pilot.pause()
            container.post_message(ImageAdded(Path("/tmp/b.png"), "data2"))
            await pilot.pause()

            assert "[Image #1]" in textarea.text
            assert "[Image #2]" in textarea.text
            assert textarea.text.index("[Image #1]") < textarea.text.index("[Image #2]")

    async def test_token_is_highlighted(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "data"))
            await pilot.pause()

            highlights = textarea._highlights[0]
            names = [name for _, _, name in highlights]
            assert "image-token" in names
            assert "image-token" in textarea._theme.syntax_styles

    async def test_backspace_inside_token_deletes_whole_token(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "data"))
            await pilot.pause()

            assert textarea.text == "[Image #1] "
            textarea.cursor_location = (0, 5)
            await pilot.press("backspace")
            await pilot.pause()

            assert "[Image #1]" not in textarea.text
            assert textarea.text == " "

    async def test_backspace_just_after_token_deletes_token(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "data"))
            await pilot.pause()

            textarea.cursor_location = (0, 10)  # right after closing "]"
            await pilot.press("backspace")
            await pilot.pause()

            assert textarea.text == " "

    async def test_delete_at_token_start_deletes_whole_token(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "data"))
            await pilot.pause()

            textarea.cursor_location = (0, 0)
            await pilot.press("delete")
            await pilot.pause()

            assert "[Image #1]" not in textarea.text

    async def test_backspace_before_token_deletes_one_char(self, chat_model):
        from oterm.app.widgets.image import ImageAdded
        from oterm.app.widgets.prompt import FlexibleInput, PostableTextArea

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            prompt = container.query_one("#prompt", FlexibleInput)
            textarea = prompt.query_one("#promptArea", PostableTextArea)
            textarea.text = "abc"
            textarea.cursor_location = (0, 3)
            await pilot.pause()

            container.post_message(ImageAdded(Path("/tmp/a.png"), "data"))
            await pilot.pause()

            assert textarea.text == "abc[Image #1] "
            textarea.cursor_location = (0, 3)
            await pilot.press("backspace")
            await pilot.pause()

            assert textarea.text == "ab[Image #1] "

    async def test_malformed_image_is_skipped_with_notification(self, chat_model):
        from oterm.app.widgets.chat import build_user_prompt

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

            user_prompt, skipped = build_user_prompt("look", [good, bad])
            assert skipped == 1

            chunks = []
            async for chunk in container.stream_agent(user_prompt):
                chunks.append(chunk)

            text = "".join(
                p.content_delta for p in chunks if isinstance(p, TextPartDelta)
            )
            assert text == "ok response"
            await pilot.pause()


class TestBuildUserPrompt:
    def test_no_tokens_no_images_returns_text(self):
        from oterm.app.widgets.chat import build_user_prompt

        assert build_user_prompt("hello", []) == ("hello", 0)

    def test_no_tokens_with_images_appends_at_end(self):
        from pydantic_ai import BinaryContent

        from oterm.app.widgets.chat import build_user_prompt

        good = base64.b64encode(b"\x89PNG\r\n").decode()
        prompt, skipped = build_user_prompt("describe", [good])
        assert skipped == 0
        assert isinstance(prompt, list)
        assert prompt[0] == "describe"
        assert isinstance(prompt[1], BinaryContent)

    def test_token_interleaves_image_at_position(self):
        from pydantic_ai import BinaryContent

        from oterm.app.widgets.chat import build_user_prompt

        good = base64.b64encode(b"\x89PNG\r\n").decode()
        prompt, skipped = build_user_prompt("see [Image #1] please", [good])
        assert skipped == 0
        assert isinstance(prompt, list)
        assert prompt[0] == "see "
        assert isinstance(prompt[1], BinaryContent)
        assert prompt[2] == " please"

    def test_unreferenced_image_is_dropped_when_tokens_present(self):
        from pydantic_ai import BinaryContent

        from oterm.app.widgets.chat import build_user_prompt

        good1 = base64.b64encode(b"\x89PNG\r\n1").decode()
        good2 = base64.b64encode(b"\x89PNG\r\n2").decode()
        prompt, skipped = build_user_prompt("[Image #2] only", [good1, good2])
        assert skipped == 0
        assert isinstance(prompt, list)
        # Only image #2 is referenced; image #1 is not appended.
        binaries = [p for p in prompt if isinstance(p, BinaryContent)]
        assert len(binaries) == 1

    def test_invalid_token_index_preserved_as_literal(self):
        from oterm.app.widgets.chat import build_user_prompt

        prompt, skipped = build_user_prompt("[Image #5] hi", [])
        assert skipped == 0
        assert prompt == "[Image #5] hi"

    def test_no_token_all_invalid_b64_returns_text(self):
        from oterm.app.widgets.chat import build_user_prompt

        prompt, skipped = build_user_prompt("describe", ["not-valid!!"])
        assert skipped == 1
        assert prompt == "describe"

    def test_token_with_invalid_b64_increments_skipped(self):
        from oterm.app.widgets.chat import build_user_prompt

        prompt, skipped = build_user_prompt("see [Image #1]", ["not-valid!!"])
        assert skipped == 1
        assert prompt == "see [Image #1]"

    def test_text_ending_at_token_keeps_no_trailing(self):
        from pydantic_ai import BinaryContent

        from oterm.app.widgets.chat import build_user_prompt

        good = base64.b64encode(b"\x89PNG\r\n").decode()
        prompt, skipped = build_user_prompt("see [Image #1]", [good])
        assert skipped == 0
        assert isinstance(prompt, list)
        assert prompt[-1].__class__ is BinaryContent  # no trailing text part


class TestPydanticHistoryRebuild:
    async def test_user_message_with_token_replays_image_inline(
        self, store, chat_model
    ):
        from pydantic_ai import BinaryContent
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        good = base64.b64encode(b"\x89PNG\r\n").decode()
        msg = MessageModel(
            chat_id=chat_id,
            role="user",
            text="see [Image #1] please",
            images=[good],
        )
        msg.id = await store.save_message(msg)

        app = _Host(chat_model, [msg])
        async with app.run_test():
            container = app.query_one(ChatContainer)
            history = container.pydantic_history
            assert len(history) == 1
            req = history[0]
            assert isinstance(req, ModelRequest)
            user_part = req.parts[0]
            assert isinstance(user_part, UserPromptPart)
            assert isinstance(user_part.content, list)
            assert any(isinstance(p, BinaryContent) for p in user_part.content)

    async def test_legacy_user_message_without_tokens_appends_images(
        self, store, chat_model
    ):
        from pydantic_ai import BinaryContent
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        good = base64.b64encode(b"\x89PNG\r\n").decode()
        msg = MessageModel(
            chat_id=chat_id,
            role="user",
            text="describe",
            images=[good],
        )
        msg.id = await store.save_message(msg)

        app = _Host(chat_model, [msg])
        async with app.run_test():
            container = app.query_one(ChatContainer)
            req = container.pydantic_history[0]
            assert isinstance(req, ModelRequest)
            user_part = req.parts[0]
            assert isinstance(user_part, UserPromptPart)
            assert isinstance(user_part.content, list)
            assert user_part.content[0] == "describe"
            assert isinstance(user_part.content[1], BinaryContent)

    async def test_text_only_user_message_replays_as_string(self, store, chat_model):
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        msg = MessageModel(chat_id=chat_id, role="user", text="hi", images=[])
        msg.id = await store.save_message(msg)

        app = _Host(chat_model, [msg])
        async with app.run_test():
            container = app.query_one(ChatContainer)
            req = container.pydantic_history[0]
            assert isinstance(req, ModelRequest)
            user_part = req.parts[0]
            assert isinstance(user_part, UserPromptPart)
            assert user_part.content == "hi"


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
            await wait_until(
                pilot,
                lambda: any("Cannot send" in n.message for n in _notifications(app)),
            )
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
            await wait_until(
                pilot,
                lambda: any(
                    "Unexpected error" in n.message for n in _notifications(app)
                ),
            )

            assert container.messages == []
            assert any("Unexpected error" in n.message for n in _notifications(app))
            # UsageStatus is removed when the turn fails.
            assert list(container.query(UsageStatus)) == []


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
            await wait_until(pilot, lambda: container.chat_model.system == "be terse")
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
            await wait_until(
                pilot,
                lambda: any("renamed" in n.message for n in _notifications(app)),
            )
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


class TestChatItemUser:
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


class TestThinkingCollapse:
    async def test_thinking_visible_before_response_starts(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.thinking = "musing…"
            await pilot.pause()

            from textual.widgets import Static

            label = item.query_one(".thinking-label", Static)
            body = item.query_one(".thinking-body", Markdown)
            assert label.display is True
            assert body.display is True
            assert "thinking" in str(label.render())

    async def test_thinking_collapses_when_response_starts(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.thinking = "musing…"
            await pilot.pause()
            item.text = "answer"
            await pilot.pause()

            from textual.widgets import Static

            label = item.query_one(".thinking-label", Static)
            body = item.query_one(".thinking-body", Markdown)
            assert label.display is True
            assert body.display is False
            assert "▸" in str(label.render())
            assert "thoughts" in str(label.render())

    async def test_thinking_stays_collapsed_on_further_thinking_deltas(
        self, chat_model
    ):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.thinking = "musing…"
            item.text = "answer"
            await pilot.pause()
            item.thinking = "musing… more"
            await pilot.pause()

            body = item.query_one(".thinking-body", Markdown)
            assert body.display is False

    async def test_clicking_collapsed_label_re_expands(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.thinking = "musing"
            item.text = "answer"
            await pilot.pause()

            from textual.widgets import Static

            label = item.query_one(".thinking-label", Static)
            body = item.query_one(".thinking-body", Markdown)
            assert body.display is False

            copied: list[str] = []
            app.copy_to_clipboard = lambda t: copied.append(t)  # ty: ignore[invalid-assignment]

            await pilot.click(label)
            await pilot.pause()
            assert body.display is True
            assert "▾" in str(label.render())
            assert copied == []

            await pilot.click(label)
            await pilot.pause()
            assert body.display is False
            assert "▸" in str(label.render())

    async def test_clicking_response_still_copies(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            item.thinking = "musing"
            item.text = "answer"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            copied: list[str] = []
            app.copy_to_clipboard = lambda t: copied.append(t)  # ty: ignore[invalid-assignment]

            response = item.query_one(".response", Markdown)
            await pilot.click(response)
            await pilot.pause()
            assert copied == ["answer"]

    async def test_clicking_thinking_label_without_text_does_not_toggle(
        self, chat_model
    ):
        from textual.widgets import Static

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            item.thinking = "still thinking"
            await pilot.pause()
            label = item.query_one(".thinking-label", Static)
            assert item.thoughts_collapsed is False

            copied: list[str] = []
            app.copy_to_clipboard = lambda t: copied.append(t)  # ty: ignore[invalid-assignment]

            await pilot.click(label)
            await pilot.pause()
            # Click on label returns early — no toggle, no copy.
            assert item.thoughts_collapsed is False
            assert copied == []

    async def test_clicking_thinking_body_does_not_copy(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            item.thinking = "musing"
            item.text = "answer"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()
            # Surface the body so it can receive a click.
            item.thoughts_collapsed = False
            await pilot.pause()

            copied: list[str] = []
            app.copy_to_clipboard = lambda t: copied.append(t)  # ty: ignore[invalid-assignment]

            body = item.query_one(".thinking-body", Markdown)
            await pilot.click(body)
            await pilot.pause()
            assert copied == []


class TestUserItemClick:
    async def test_clicking_user_item_copies_text(self, chat_model):
        from textual.widgets import Static

        app = _Host(chat_model, [])
        async with app.run_test(size=(120, 40)) as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            item.text = "my prompt"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            copied: list[str] = []
            app.copy_to_clipboard = lambda t: copied.append(t)  # ty: ignore[invalid-assignment]

            text_static = next(s for s in item.query(Static) if s.has_class("text"))
            await pilot.click(text_static)
            await pilot.pause()
            assert copied == ["my prompt"]


class TestChatItemStreaming:
    """Streaming path: append_text / append_thinking / finish_stream.

    These bypass the watch_text / watch_thinking re-render path and write
    deltas to a Textual ``MarkdownStream`` so long responses render
    incrementally instead of re-parsing the whole document per token.
    """

    async def test_append_text_updates_text_reactive(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.append_text("hello ")
            await item.append_text("world")
            await pilot.pause()

            # Reactive kept in sync for click-to-copy and chrome refresh.
            assert item.text == "hello world"

    async def test_append_text_collapses_thoughts_on_first_delta(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.append_thinking("thinking…")
            await pilot.pause()
            assert item.thoughts_collapsed is False

            await item.append_text("answer")
            await pilot.pause()
            assert item.thoughts_collapsed is True

            from textual.widgets import Static

            label = item.query_one(".thinking-label", Static)
            body = item.query_one(".thinking-body", Markdown)
            assert body.display is False
            assert "▸" in str(label.render())

    async def test_append_thinking_reveals_label_on_first_delta(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            from textual.widgets import Static

            label = item.query_one(".thinking-label", Static)
            assert label.display is False

            await item.append_thinking("musing")
            await pilot.pause()

            assert label.display is True
            assert item.thinking == "musing"

    async def test_user_item_append_is_noop(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.append_text("ignored")
            await item.append_thinking("ignored")
            await pilot.pause()

            assert item.text == ""
            assert item.thinking == ""

    async def test_finish_stream_idempotent_when_never_streamed(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.finish_stream()
            await item.finish_stream()  # safe to call twice

    async def test_cancel_streams_safe_after_appends(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.append_text("partial ")
            item.cancel_streams()
            # No exception, streams cleared.
            assert item._response_stream is None
            assert item._thinking_stream is None

    async def test_append_thinking_twice_reuses_stream(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.append_thinking("first ")
            stream = item._thinking_stream
            assert stream is not None

            await item.append_thinking("second")
            await pilot.pause()
            # Second call must reuse the same MarkdownStream, not recreate one.
            assert item._thinking_stream is stream
            assert item.thinking == "first second"

    async def test_finish_stream_drains_thinking_stream(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.append_thinking("musing")
            assert item._thinking_stream is not None
            await item.finish_stream()
            assert item._thinking_stream is None


class TestSkippedImageNotify:
    async def test_response_task_notifies_for_malformed_image(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "ok "
            yield "done"

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))
            container.images = [(Path("/tmp/x.png"), "not-valid!!")]

            prompt = app.query_one(FlexibleInput)
            prompt.text = "see [Image #1]"
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(container.messages) == 2)
            assert any(
                "Skipped 1 malformed image" in n.message for n in _notifications(app)
            )

    async def test_regenerate_notifies_for_malformed_image(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(
            chat_id=chat_id,
            role="user",
            text="see [Image #1]",
            images=["not-valid!!"],
        )
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
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
            assert any(
                "Skipped 1 malformed image" in n.message for n in _notifications(app)
            )


class TestThinkingViaResponseTask:
    async def test_thinking_then_text_streams_through_response_task(
        self, store, chat_model
    ):
        from pydantic_ai.models.function import DeltaThinkingPart

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaThinkingPart]]:
            yield {0: DeltaThinkingPart(content="weighing… ")}
            yield {0: DeltaThinkingPart(content="options")}
            yield "the "
            yield "answer"

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            prompt = app.query_one(FlexibleInput)
            prompt.text = "ask"
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(container.messages) == 2)

            assert container.messages[-1].text == "the answer"
            items = list(container.query(ChatItem))
            assistant = items[-1]
            assert "weighing… options" in assistant.thinking

    async def test_tool_call_renders_inside_assistant_item(self, store, chat_model):
        from pydantic_ai import Tool
        from pydantic_ai.models.function import DeltaToolCall

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        def echo(s: str) -> str:
            return f"echoed: {s}"

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
            already_called = any(
                getattr(m, "parts", None)
                and any(getattr(p, "part_kind", "") == "tool-return" for p in m.parts)
                for m in messages
            )
            if already_called:
                yield "all done"
                return
            yield {
                0: DeltaToolCall(
                    name="echo", json_args='{"s": "hi"}', tool_call_id="tc-1"
                )
            }

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(
                FunctionModel(stream_function=stream_fn), tools=[Tool(echo)]
            )

            prompt = app.query_one(FlexibleInput)
            prompt.text = "go"
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(container.messages) == 2)

            from textual.widgets import Static

            assistant = list(container.query(ChatItem))[-1]
            tool_items = list(assistant.query(ToolCallItem))
            assert len(tool_items) == 1
            tool_item = tool_items[0]
            assert tool_item.tool_name == "echo"
            assert tool_item.tool_call_id == "tc-1"
            assert tool_item.result == "echoed: hi"

            header = tool_item.query_one(".tool-call-header", Static)
            assert "▸ tool call: echo" in str(header.render())
            # Click the tool-call to expand; args + result should land in body.
            await pilot.click(ToolCallItem)
            await pilot.pause()
            body_text = _capture(tool_item.query_one(".tool-call-body", Static).content)
            assert '"s": "hi"' in body_text
            assert "echoed: hi" in body_text
            assert "args:" in body_text
            assert "result:" in body_text
            assert "▾ tool call: echo" in str(header.render())

    async def test_file_part_streamed_through_response_task(self, store, chat_model):
        """A `FilePart` arrives during streaming and renders as an Image widget."""
        from io import BytesIO

        from PIL import Image as PILImage
        from pydantic_ai.messages import BinaryImage, FilePart
        from textual_image.widget import Image as ImageWidget

        from tests._stream_helpers import make_file_aware_agent

        buf = BytesIO()
        PILImage.new("RGB", (4, 4), "red").save(buf, format="PNG")
        png_bytes = buf.getvalue()

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | FilePart]:
            yield "before "
            yield FilePart(content=BinaryImage(data=png_bytes, media_type="image/png"))
            yield "after"

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = make_file_aware_agent(stream_fn)

            prompt = app.query_one(FlexibleInput)
            prompt.text = "draw"
            await pilot.press("enter")
            await wait_until(pilot, lambda: len(container.messages) == 2)

            assert container.messages[-1].text == "before after"
            assistant = list(container.query(ChatItem))[-1]
            images = list(assistant.query(ImageWidget))
            assert len(images) == 1
            assert images[0].image is not None

            # Persisted: the assistant row carries the image as base64.
            assistant_row = container.messages[-1]
            assert len(assistant_row.images) == 1
            assert base64.b64decode(assistant_row.images[0]) == png_bytes
            stored = await store.get_messages(chat_id)
            assistant_rows = [m for m in stored if m.role == "assistant"]
            assert len(assistant_rows[0].images) == 1

    async def test_persisted_assistant_image_renders_on_load(self, store, chat_model):
        from io import BytesIO

        from PIL import Image as PILImage
        from textual_image.widget import Image as ImageWidget

        buf = BytesIO()
        PILImage.new("RGB", (4, 4), "blue").save(buf, format="PNG")
        png_bytes = buf.getvalue()

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="draw")
        user_msg.id = await store.save_message(user_msg)
        assistant_msg = MessageModel(
            chat_id=chat_id,
            role="assistant",
            text="here you go",
            images=[base64.b64encode(png_bytes).decode()],
        )
        assistant_msg.id = await store.save_message(assistant_msg)

        app = _Host(chat_model, [user_msg, assistant_msg])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            await pilot.pause()

            items = list(container.query(ChatItem))
            assert items[-1].author == "assistant"
            images = list(items[-1].query(ImageWidget))
            assert len(images) == 1
            assert images[0].image is not None


class TestRegenerateCancellation:
    async def test_cancellation_restores_state(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="ask")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            raise asyncio.CancelledError()
            yield  # pragma: no cover

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await wait_until(pilot, lambda: container.messages[-1].text == "old")
            assert container.messages[-1].text == "old"
            assert list(container.query(UsageStatus)) == []


class TestToolCallHelpers:
    def test_truncate_keeps_short_text(self):
        assert _truncate("short", 10) == "short"

    def test_truncate_appends_ellipsis(self):
        assert _truncate("abcdefghij", 5) == "abcde…"

    @pytest.mark.parametrize(
        ("value", "expected_type", "expected_substring"),
        [
            ({"a": 1}, JSON, None),
            ('{"a": 1}', JSON, None),
            ("hello world", Text, "hello"),
            (None, Text, "(none)"),
            (42, Text, "42"),
        ],
    )
    def test_format_value_dispatches_by_type(
        self, value, expected_type, expected_substring
    ):
        rendered = _format_value(value)
        assert isinstance(rendered, expected_type)
        if expected_substring is not None:
            assert expected_substring in rendered.plain


class TestToolCallRendering:
    async def test_add_tool_call_is_a_no_op_for_user_items(self, chat_model):
        from pydantic_ai.messages import ToolCallPart

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.add_tool_call(
                ToolCallPart(tool_name="x", args="{}", tool_call_id="tc-x")
            )
            assert list(item.query(ToolCallItem)) == []

    async def test_add_image_is_a_no_op_for_user_items(self, chat_model):
        from textual_image.widget import Image as ImageWidget

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "user"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.add_image(b"\x89PNG\r\n")
            assert list(item.query(ImageWidget)) == []

    async def test_clicking_assistant_image_saves_it_to_disk(
        self, chat_model, tmp_path, monkeypatch
    ):
        from io import BytesIO

        from PIL import Image as PILImage
        from textual_image.widget import Image as ImageWidget

        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OTERM_DATA_DIR", tmp_path)

        buf = BytesIO()
        PILImage.new("RGB", (4, 4), "lime").save(buf, format="PNG")
        png_bytes = buf.getvalue()

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.add_image(png_bytes)
            await pilot.pause()
            assistant_image = item.query_one(".assistantImage", ImageWidget)
            await item._save_assistant_image(assistant_image)
            await pilot.pause()

            saved = list((tmp_path / "downloads").iterdir())
            assert len(saved) == 1
            assert saved[0].read_bytes() == png_bytes
            assert saved[0].suffix == ".png"
            assert any("Image saved" in n.message for n in _notifications(app))

    async def test_jpeg_assistant_image_saves_with_jpg_extension(
        self, chat_model, tmp_path, monkeypatch
    ):
        from io import BytesIO

        from PIL import Image as PILImage
        from textual_image.widget import Image as ImageWidget

        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OTERM_DATA_DIR", tmp_path)

        buf = BytesIO()
        PILImage.new("RGB", (4, 4), "orange").save(buf, format="JPEG")
        jpg_bytes = buf.getvalue()

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.add_image(jpg_bytes)
            await pilot.pause()
            await item._save_assistant_image(
                item.query_one(".assistantImage", ImageWidget)
            )

            saved = list((tmp_path / "downloads").iterdir())
            assert len(saved) == 1
            assert saved[0].suffix == ".jpg"

    async def test_chat_item_click_on_image_dispatches_save(
        self, chat_model, tmp_path, monkeypatch
    ):
        from io import BytesIO

        from PIL import Image as PILImage
        from textual.events import Click
        from textual_image.widget import Image as ImageWidget

        import oterm.config

        monkeypatch.setattr(oterm.config.envConfig, "OTERM_DATA_DIR", tmp_path)

        buf = BytesIO()
        PILImage.new("RGB", (4, 4), "navy").save(buf, format="PNG")
        png_bytes = buf.getvalue()

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.add_image(png_bytes)
            await pilot.pause()
            assistant_image = item.query_one(".assistantImage", ImageWidget)

            click = Click(
                widget=assistant_image,
                x=0,
                y=0,
                delta_x=0,
                delta_y=0,
                button=1,
                shift=False,
                meta=False,
                ctrl=False,
            )
            await item.on_click(click)
            await pilot.pause()

            saved = list((tmp_path / "downloads").iterdir())
            assert len(saved) == 1
            assert saved[0].read_bytes() == png_bytes

    async def test_expand_before_result_shows_only_args(self, chat_model):
        from pydantic_ai.messages import ToolCallPart
        from textual.widgets import Static

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            item = ChatItem()
            item.author = "assistant"
            await container.query_one("#messageContainer").mount(item)
            await pilot.pause()

            await item.add_tool_call(
                ToolCallPart(tool_name="search", args='{"q": "x"}', tool_call_id="tc-1")
            )
            tool_item = item.query_one(ToolCallItem)
            tool_item.collapsed = False
            await pilot.pause()

            body_text = _capture(tool_item.query_one(".tool-call-body", Static).content)
            assert '"q": "x"' in body_text
            assert "args:" in body_text
            assert "result:" not in body_text


def _capture(renderable) -> str:
    """Render a Rich renderable to plain text without ANSI styling."""
    console = Console(width=80, color_system=None)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TestUsageStatus:
    async def test_zero_tokens_render_only_duration(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            status = UsageStatus()
            await container.query_one("#messageContainer").mount(status)
            await pilot.pause()

            rendered = str(status.render())
            assert "↑" not in rendered
            assert "↓" not in rendered
            assert rendered.endswith("s")

    async def test_tick_advances_spinner_frame(self, chat_model):
        """Direct call so we don't depend on the 0.1s timer firing in time."""
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            status = UsageStatus()
            await container.query_one("#messageContainer").mount(status)
            await pilot.pause()

            before = status._frame
            status._tick()
            assert status._frame == (before + 1) % len(UsageStatus.SPINNER_FRAMES)

    async def test_update_usage_renders_token_arrows(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            status = UsageStatus()
            await container.query_one("#messageContainer").mount(status)
            await pilot.pause()

            status.update_usage(input_tokens=42, output_tokens=7)
            await pilot.pause()
            rendered = str(status.render())
            assert "↑ 42" in rendered
            assert "↓ 7" in rendered

    async def test_finish_drops_spinner_glyph(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            status = UsageStatus()
            await container.query_one("#messageContainer").mount(status)
            await pilot.pause()

            status.update_usage(input_tokens=10, output_tokens=5)
            status.finish()
            await pilot.pause()

            rendered = str(status.render())
            assert not any(frame in rendered for frame in UsageStatus.SPINNER_FRAMES)
            assert "↑ 10" in rendered
            assert "↓ 5" in rendered

    async def test_finish_is_idempotent(self, chat_model):
        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            status = UsageStatus()
            await container.query_one("#messageContainer").mount(status)
            await pilot.pause()
            status.finish()
            # Second finish is a no-op — must not raise even with the timer gone.
            status.finish()

    async def test_status_persists_after_successful_turn(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "first "
            yield "second"

        app = _Host(chat_model, [])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            prompt = app.query_one(FlexibleInput)
            prompt.text = "hello"
            await pilot.press("enter")

            await wait_until(pilot, lambda: len(container.messages) == 2)

            statuses = list(container.query(UsageStatus))
            assert len(statuses) == 1
            # After success, the spinner glyph is gone but the line remains.
            rendered = str(statuses[0].render())
            assert not any(frame in rendered for frame in UsageStatus.SPINNER_FRAMES)
