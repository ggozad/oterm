import asyncio
import base64
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from textual.app import App, ComposeResult
from textual.widgets import Markdown

from oterm.app.widgets.chat import ChatContainer, ChatItem, UsageStatus
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

            assert chunks[-1] == ("", "ok response")
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
            assert "Thinking" in str(label.render())

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
            assert "Thoughts" in str(label.render())

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

            for _ in range(50):
                await asyncio.sleep(0)
                await pilot.pause()
                if len(container.messages) == 2:
                    break

            statuses = list(container.query(UsageStatus))
            assert len(statuses) == 1
            # After success, the spinner glyph is gone but the line remains.
            rendered = str(statuses[0].render())
            assert not any(frame in rendered for frame in UsageStatus.SPINNER_FRAMES)
