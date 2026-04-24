from collections.abc import AsyncIterator

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, FunctionModel
from textual.app import App, ComposeResult

from oterm.app.widgets.chat import ChatContainer
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
            await pilot.pause()
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
            await pilot.pause()

            assert len(container.messages) == 2
            assert container.messages[-1].role == "assistant"
            assert container.messages[-1].text == "new answer"

            stored = await store.get_messages(chat_id)
            assistant_rows = [m for m in stored if m.role == "assistant"]
            assert len(assistant_rows) == 1
            assert assistant_rows[0].text == "new answer"


class TestRegenerateErrorRestore:
    async def test_empty_response_restores_state(self, store, chat_model):
        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id
        user_msg = MessageModel(chat_id=chat_id, role="user", text="q")
        user_msg.id = await store.save_message(user_msg)
        old_assistant = MessageModel(chat_id=chat_id, role="assistant", text="old")
        old_assistant.id = await store.save_message(old_assistant)

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            # Single token only → PartStartEvent but no PartDeltaEvent → stream_agent
            # yields no chunks → regenerate sees an empty response.
            yield "only"

        app = _Host(chat_model, [user_msg, old_assistant])
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            await container.load_messages()
            container.agent = Agent(FunctionModel(stream_function=stream_fn))

            await container.action_regenerate_llm_message()
            await pilot.pause()

            assert container.messages[-1].text == "old"
            assert any("No response received" in n.message for n in _notifications(app))

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
            await pilot.pause()

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
            await pilot.pause()

            assert container.messages[-1].text == "old"
            assert any(
                "error running your request" in n.message for n in _notifications(app)
            )
