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

    def test_mcp_tools_become_filtered_toolset(self, monkeypatch):
        class _FakeServer:
            def __init__(self) -> None:
                self.filtered_args: list = []

            def filtered(self, predicate):
                self.filtered_args.append(predicate)
                return f"toolset-{id(predicate)}"

        server = _FakeServer()
        monkeypatch.setattr("oterm.app.widgets.chat.builtin_tools", [])
        monkeypatch.setattr(
            "oterm.app.widgets.chat.mcp_tool_meta",
            {"oracle": [{"name": "ask_oracle", "description": ""}]},
        )
        monkeypatch.setattr("oterm.app.widgets.chat.mcp_servers", {"oracle": server})
        tools, toolsets = _resolve_tools(["ask_oracle"])
        assert tools == []
        assert len(toolsets) == 1
        # The filter predicate accepts the chosen tool name and rejects others.
        from types import SimpleNamespace

        predicate = server.filtered_args[0]
        assert predicate(None, SimpleNamespace(name="ask_oracle")) is True
        assert predicate(None, SimpleNamespace(name="other")) is False


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


class TestResponseTaskErrors:
    async def test_model_http_error_notifies(self, store, chat_model):
        from collections.abc import AsyncIterator

        from pydantic_ai import Agent
        from pydantic_ai.exceptions import ModelHTTPError
        from pydantic_ai.messages import ModelMessage
        from pydantic_ai.models.function import AgentInfo, FunctionModel
        from textual.app import App, ComposeResult

        chat_id = await store.save_chat(chat_model)
        chat_model.id = chat_id

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            raise ModelHTTPError(status_code=500, model_name="x", body="boom")
            yield  # pragma: no cover

        class _Host(App):
            def compose(self) -> ComposeResult:
                yield ChatContainer(chat_model=chat_model, messages=[])

        app = _Host()
        async with app.run_test() as pilot:
            container = app.query_one(ChatContainer)
            container.agent = Agent(FunctionModel(stream_function=stream_fn))
            await container.response_task("hello")
            await pilot.pause()
            assert any(
                "error running your request" in n.message
                for n in list(app._notifications)
            )
            stored = await store.get_messages(chat_id)
            assert stored == []
            assert container.messages == []
