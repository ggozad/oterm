import pytest
from pydantic_ai import Tool as PydanticTool

from oterm.app.widgets.chat import ChatContainer, _resolve_tools
from oterm.types import ChatModel


class TestResolveTools:
    def test_empty_returns_empty(self):
        tools, toolsets = _resolve_tools([])
        assert tools == []
        assert toolsets == []

    def test_unknown_tool_logged_and_dropped(self, monkeypatch):
        import oterm.log

        monkeypatch.setattr("oterm.app.widgets.chat.builtin_tools", [])
        monkeypatch.setattr("oterm.app.widgets.chat.mcp_tool_meta", {})
        before = len(oterm.log.log_lines)
        tools, toolsets = _resolve_tools(["ghost"])
        assert tools == []
        assert toolsets == []
        messages = [msg for _, msg in oterm.log.log_lines[before:]]
        assert any("unavailable tools" in m and "ghost" in m for m in messages)

    def test_known_tool_returned(self, monkeypatch):
        def sample() -> str:
            return "x"

        tool = PydanticTool(sample, takes_ctx=False)
        monkeypatch.setattr(
            "oterm.app.widgets.chat.builtin_tools",
            [{"name": "sample", "description": "", "tool": tool}],
        )
        monkeypatch.setattr("oterm.app.widgets.chat.mcp_tool_meta", {})
        tools, toolsets = _resolve_tools(["sample"])
        assert tools == [tool]
        assert toolsets == []


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
