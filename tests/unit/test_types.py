import pytest
from pydantic import ValidationError

from oterm.types import ChatModel, MessageModel, ParsedResponse


def test_chat_model_defaults():
    chat = ChatModel(model="llama3")
    assert chat.id is None
    assert chat.name == ""
    assert chat.model == "llama3"
    assert chat.system is None
    assert chat.provider == "ollama"
    assert chat.parameters == {}
    assert chat.tools == []
    assert chat.thinking is False


def test_chat_model_fields_populated():
    chat = ChatModel(
        id=7,
        name="c7",
        model="qwen",
        system="be helpful",
        provider="anthropic",
        parameters={"temperature": 0.3},
        tools=["date_time"],
        thinking=True,
    )
    assert chat.id == 7
    assert chat.tools == ["date_time"]
    assert chat.parameters["temperature"] == 0.3


def test_message_model_requires_chat_id_and_role():
    with pytest.raises(ValidationError):
        MessageModel(text="hi")  # ty: ignore[missing-argument]


def test_message_model_rejects_unknown_role():
    with pytest.raises(ValidationError):
        MessageModel(chat_id=1, role="robot", text="x")  # ty: ignore[invalid-argument-type]


def test_message_model_roundtrip():
    msg = MessageModel(chat_id=3, role="assistant", text="hello", images=["b64data"])
    dumped = msg.model_dump()
    assert dumped["role"] == "assistant"
    assert dumped["images"] == ["b64data"]
    assert MessageModel(**dumped) == msg


def test_parsed_response_fields():
    p = ParsedResponse(thought="t", response="r", formatted_output="f")
    assert p.thought == "t"
    assert p.response == "r"
    assert p.formatted_output == "f"
