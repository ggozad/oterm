from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from oterm.app.widgets.chat import ChatContainer
from oterm.types import ChatModel, MessageModel


def _container(messages):
    return ChatContainer(
        chat_model=ChatModel(model="m", provider="ollama"), messages=messages
    )


def test_empty_history():
    assert _container([])._build_pydantic_history([]) == []


def test_user_messages_become_model_requests():
    msgs = [MessageModel(chat_id=1, role="user", text="hi")]
    history = _container(msgs)._build_pydantic_history(msgs)
    assert len(history) == 1
    assert isinstance(history[0], ModelRequest)
    assert isinstance(history[0].parts[0], UserPromptPart)
    assert history[0].parts[0].content == "hi"


def test_assistant_messages_become_model_responses():
    msgs = [MessageModel(chat_id=1, role="assistant", text="answer")]
    history = _container(msgs)._build_pydantic_history(msgs)
    assert len(history) == 1
    assert isinstance(history[0], ModelResponse)
    assert isinstance(history[0].parts[0], TextPart)
    assert history[0].parts[0].content == "answer"


def test_system_and_tool_roles_are_skipped():
    msgs = [
        MessageModel(chat_id=1, role="user", text="u"),
        MessageModel(chat_id=1, role="system", text="s"),
        MessageModel(chat_id=1, role="tool", text="t"),
        MessageModel(chat_id=1, role="assistant", text="a"),
    ]
    history = _container(msgs)._build_pydantic_history(msgs)
    assert len(history) == 2
    assert isinstance(history[0], ModelRequest)
    assert isinstance(history[1], ModelResponse)


def test_alternating_conversation_preserved():
    msgs = [
        MessageModel(chat_id=1, role="user", text="q1"),
        MessageModel(chat_id=1, role="assistant", text="a1"),
        MessageModel(chat_id=1, role="user", text="q2"),
        MessageModel(chat_id=1, role="assistant", text="a2"),
    ]
    history = _container(msgs)._build_pydantic_history(msgs)
    assert len(history) == 4
    contents = [p.parts[0].content for p in history]
    assert contents == ["q1", "a1", "q2", "a2"]
