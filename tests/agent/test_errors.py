import pytest
from pydantic_ai import Tool as PydanticTool

from oterm.app.widgets.chat import ChatContainer, _resolve_tools
from oterm.types import ChatModel


class TestResolveTools:
    def test_empty_returns_empty(self):
        assert _resolve_tools([]) == []

    def test_unknown_tool_logged_and_dropped(self, monkeypatch):
        import oterm.log

        monkeypatch.setattr("oterm.app.widgets.chat.available_tools", lambda: [])
        before = len(oterm.log.log_lines)
        tools = _resolve_tools(["ghost"])
        assert tools == []
        messages = [msg for _, msg in oterm.log.log_lines[before:]]
        assert any("unavailable tools" in m and "ghost" in m for m in messages)

    def test_known_tool_returned(self, monkeypatch):
        def sample() -> str:
            return "x"

        tool = PydanticTool(sample, takes_ctx=False)
        monkeypatch.setattr(
            "oterm.app.widgets.chat.available_tools",
            lambda: [{"name": "sample", "description": "", "tool": tool}],
        )
        assert _resolve_tools(["sample"]) == [tool]


class TestRebuildAgent:
    def test_success_populates_agent(self):
        cm = ChatModel(model="llama3", provider="ollama")
        container = ChatContainer(chat_model=cm, messages=[])
        assert container.agent is not None
        assert container._agent_error is None

    def test_failure_captures_error_message(self, app_config):
        cm = ChatModel(model="m", provider="openai-compat/does-not-exist")
        container = ChatContainer(chat_model=cm, messages=[])
        assert container.agent is None
        assert container._agent_error is not None
        assert "not configured" in container._agent_error


class TestStreamAgentGuards:
    async def test_stream_agent_raises_when_agent_is_none(self, app_config):
        cm = ChatModel(model="m", provider="openai-compat/missing")
        container = ChatContainer(chat_model=cm, messages=[])
        assert container.agent is None

        with pytest.raises(RuntimeError, match="not configured"):
            async for _ in container.stream_agent("hello"):
                pass
