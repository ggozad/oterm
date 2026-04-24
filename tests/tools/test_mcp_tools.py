from mcp.types import EmbeddedResource, ImageContent, TextContent, TextResourceContents
from pydantic import AnyUrl

from oterm.tools.mcp.tools import MCPToolCallable, mcp_tool_to_pydantic_tool


class _FakeMCPClient:
    def __init__(self, response):
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self._response


class TestMCPToolCallable:
    async def test_joins_text_content(self):
        client = _FakeMCPClient(
            [TextContent(type="text", text="one"), TextContent(type="text", text="two")]
        )
        callable_ = MCPToolCallable("oracle", "server", client)  # ty: ignore[invalid-argument-type]

        result = await callable_.call(question="x")
        assert result == "one\ntwo"
        assert client.calls == [("oracle", {"question": "x"})]

    async def test_ignores_non_text_content(self):
        client = _FakeMCPClient(
            [
                TextContent(type="text", text="hi"),
                ImageContent(type="image", data="base64==", mimeType="image/png"),
                EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(
                        uri=AnyUrl("file:///x"), text="doc", mimeType="text/plain"
                    ),
                ),
            ]
        )
        callable_ = MCPToolCallable("t", "s", client)  # ty: ignore[invalid-argument-type]
        result = await callable_.call()
        assert result == "hi"


class TestMcpToolToPydanticTool:
    def test_schema_and_description_passed_through(self):
        from mcp import Tool as MCPTool

        mcp_tool = MCPTool(
            name="oracle",
            description="Ask the oracle a question.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        )

        client = _FakeMCPClient([TextContent(type="text", text="oterm")])
        callable_ = MCPToolCallable("oracle", "server", client)  # ty: ignore[invalid-argument-type]

        tool = mcp_tool_to_pydantic_tool(mcp_tool, callable_)
        assert tool.name == "oracle"
        assert tool.description == "Ask the oracle a question."
        # The pydantic-ai tool advertises the MCP inputSchema verbatim.
        assert tool.function_schema.json_schema["properties"] == {
            "query": {"type": "string"}
        }

    def test_missing_description_becomes_empty_string(self):
        from mcp import Tool as MCPTool

        mcp_tool = MCPTool(name="t", inputSchema={"type": "object", "properties": {}})
        client = _FakeMCPClient([])
        callable_ = MCPToolCallable("t", "s", client)  # ty: ignore[invalid-argument-type]

        tool = mcp_tool_to_pydantic_tool(mcp_tool, callable_)
        assert tool.description == ""
