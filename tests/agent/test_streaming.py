import base64
from collections.abc import AsyncIterator

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.function import AgentInfo, DeltaThinkingPart, FunctionModel

from oterm.app.widgets.chat import ChatContainer
from oterm.types import ChatModel


def _container() -> ChatContainer:
    return ChatContainer(
        chat_model=ChatModel(model="m", provider="ollama"), messages=[]
    )


def _install_stream_agent(container: ChatContainer, stream_fn):
    container.agent = Agent(FunctionModel(stream_function=stream_fn))


async def _collect(gen):
    out = []
    async for chunk in gen:
        out.append(chunk)
    return out


class TestTextStreaming:
    async def test_text_deltas_are_accumulated(self):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            for token in ("Hello ", "world", "!"):
                yield token

        c = _container()
        _install_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("hi"))
        # First token arrives via PartStartEvent (no yield), then each delta
        # triggers a cumulative (thinking, text) yield. With no thinking
        # content, the thinking slot stays empty.
        assert chunks == [("", "Hello world"), ("", "Hello world!")]

    async def test_single_token_produces_no_chunks(self):
        """With only a PartStartEvent and no deltas, stream_agent yields nothing."""

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "only"

        c = _container()
        _install_stream_agent(c, stream_fn)

        assert await _collect(c.stream_agent("hi")) == []


class TestThinkingStreaming:
    async def test_thinking_and_text_yielded_separately(self):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaThinkingPart]]:
            yield {0: DeltaThinkingPart(content="because ")}
            yield {0: DeltaThinkingPart(content="reasons")}
            yield "answer "
            yield "here"

        c = _container()
        _install_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("q"))
        assert chunks[-1] == ("because reasons", "answer here")
        # Thinking accumulates before text begins.
        thinking_values = {th for th, _ in chunks}
        assert "because reasons" in thinking_values


class TestHistoryUpdate:
    async def test_pydantic_history_populated_after_run(self):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "done"

        c = _container()
        _install_stream_agent(c, stream_fn)
        assert c.pydantic_history == []

        await _collect(c.stream_agent("hello"))
        # One request + one response = at least 2 messages.
        assert len(c.pydantic_history) >= 2


class TestResolveTools:
    def test_empty_intersection_with_mcp_server_skips_filter(self, monkeypatch):
        """When selected tools don't overlap a server's tools, no toolset is built.

        Drives the false branch where ``chosen = selected & names_on_server`` is
        empty: the loop iterates the server entry but skips ``filtered`` (line 153).
        """
        from oterm.app.widgets import chat as chat_mod
        from oterm.tools.mcp.setup import ToolMeta

        monkeypatch.setattr(
            chat_mod,
            "mcp_tool_meta",
            {"server_a": [ToolMeta(name="other_tool", description="x")]},
        )
        monkeypatch.setattr(chat_mod, "mcp_servers", {})
        monkeypatch.setattr(chat_mod, "builtin_tools", [])

        tools, toolsets = chat_mod._resolve_tools(["nonexistent"])
        assert tools == []
        assert toolsets == []


class TestImagePrompt:
    async def test_valid_base64_image_accepted(self):
        from oterm.app.widgets.chat import build_user_prompt

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "see"
            yield " this"

        c = _container()
        _install_stream_agent(c, stream_fn)

        img_b64 = base64.b64encode(b"\x89PNG\r\n").decode()
        user_prompt, _ = build_user_prompt("what is this?", [img_b64])
        chunks = await _collect(c.stream_agent(user_prompt))
        assert chunks[-1] == ("", "see this")
