import base64
from collections.abc import AsyncIterator

from pydantic_ai import Agent, Tool
from pydantic_ai.messages import (
    BinaryImage,
    FilePart,
    ModelMessage,
    TextPartDelta,
    ThinkingPartDelta,
    ToolCallPart,
)
from pydantic_ai.models.function import (
    AgentInfo,
    DeltaThinkingPart,
    DeltaToolCall,
    FunctionModel,
)

from oterm.app.widgets.chat import ChatContainer
from oterm.types import ChatModel
from tests._stream_helpers import make_file_aware_agent


def _container() -> ChatContainer:
    return ChatContainer(
        chat_model=ChatModel(model="m", provider="ollama"), messages=[]
    )


def _install_stream_agent(container: ChatContainer, stream_fn):
    container.agent = Agent(FunctionModel(stream_function=stream_fn))


def _install_file_aware_stream_agent(container: ChatContainer, stream_fn):
    container.agent = make_file_aware_agent(stream_fn)


async def _collect(gen):
    out = []
    async for chunk in gen:
        out.append(chunk)
    return out


class TestTextStreaming:
    async def test_text_deltas_yielded_in_order(self):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            for token in ("Hello ", "world", "!"):
                yield token

        c = _container()
        _install_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("hi"))
        assert all(isinstance(p, TextPartDelta) for p in chunks)
        assert "".join(p.content_delta for p in chunks) == "Hello world!"

    async def test_single_token_yields_one_delta(self):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str]:
            yield "only"

        c = _container()
        _install_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("hi"))
        assert chunks == [TextPartDelta(content_delta="only")]


class TestThinkingStreaming:
    async def test_thinking_then_text_preserved_in_order(self):
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
        thinking = "".join(
            p.content_delta for p in chunks if isinstance(p, ThinkingPartDelta)
        )
        text = "".join(p.content_delta for p in chunks if isinstance(p, TextPartDelta))
        assert thinking == "because reasons"
        assert text == "answer here"
        # Thinking arrives before text in the yielded sequence.
        first_text_index = next(
            i for i, p in enumerate(chunks) if isinstance(p, TextPartDelta)
        )
        last_thinking_index = max(
            i for i, p in enumerate(chunks) if isinstance(p, ThinkingPartDelta)
        )
        assert last_thinking_index < first_text_index


class TestEmptyAndIgnoredParts:
    async def test_empty_thinking_and_text_parts_skipped(self):
        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | dict[int, DeltaThinkingPart]]:
            yield {0: DeltaThinkingPart(content="")}
            yield ""
            yield "real"

        c = _container()
        _install_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("hi"))
        assert chunks == [TextPartDelta(content_delta="real")]


class TestFilePartStreaming:
    async def test_file_part_yielded_as_is(self):
        png_bytes = b"\x89PNG\r\nfake"
        file_part = FilePart(
            content=BinaryImage(data=png_bytes, media_type="image/png")
        )

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | FilePart]:
            yield "see "
            yield file_part
            yield "this"

        c = _container()
        _install_file_aware_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("draw"))
        files = [p for p in chunks if isinstance(p, FilePart)]
        assert len(files) == 1
        assert files[0].content.data == png_bytes
        assert files[0].content.media_type == "image/png"
        text = "".join(p.content_delta for p in chunks if isinstance(p, TextPartDelta))
        assert text == "see this"

    async def test_duplicate_file_parts_are_deduped_by_id(self):
        """OpenAI Responses streams the same image twice (partial + completed)
        under the same vendor part id; stream_agent collapses them."""
        png_bytes = b"\x89PNG\r\nfake"

        async def stream_fn(
            messages: list[ModelMessage], info: AgentInfo
        ) -> AsyncIterator[str | FilePart]:
            yield FilePart(
                content=BinaryImage(data=png_bytes, media_type="image/png"),
                id="img-42",
            )
            yield FilePart(
                content=BinaryImage(data=png_bytes, media_type="image/png"),
                id="img-42",
            )
            yield "done"

        c = _container()
        _install_file_aware_stream_agent(c, stream_fn)

        chunks = await _collect(c.stream_agent("draw"))
        files = [p for p in chunks if isinstance(p, FilePart)]
        assert len(files) == 1


class TestToolCallStreaming:
    async def test_tool_call_part_yielded(self):
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
                yield "done"
                return
            yield {
                0: DeltaToolCall(
                    name="echo", json_args='{"s": "hi"}', tool_call_id="tc-1"
                )
            }

        c = _container()
        c.agent = Agent(FunctionModel(stream_function=stream_fn), tools=[Tool(echo)])

        chunks = await _collect(c.stream_agent("call it"))
        tool_calls = [p for p in chunks if isinstance(p, ToolCallPart)]
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == "echo"


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
        text = "".join(p.content_delta for p in chunks if isinstance(p, TextPartDelta))
        assert text == "see this"
