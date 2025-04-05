import pytest
from mcp.types import Tool as MCPTool

from oterm.ollamaclient import OllamaLLM
from oterm.tools.mcp.tools import MCPToolCallable
from oterm.types import Tool


@pytest.mark.asyncio
async def test_mcp_tools(mcp_client):
    tools = await mcp_client.get_available_tools()
    for tool in tools:
        assert MCPTool.model_validate(tool)

    tool = tools[0]
    oterm_tool = Tool(
        function=Tool.Function(
            name=tool.name,
            description=tool.description,
            parameters=Tool.Function.Parameters.model_validate(tool.inputSchema),
        ),
    )

    mcpToolCallable = MCPToolCallable(tool.name, "test_server", mcp_client)
    llm = OllamaLLM(
        tool_defs=[{"tool": oterm_tool, "callable": mcpToolCallable.call}],
    )

    res = await llm.completion("Ask the oracle what is the best client for Ollama.")
    assert "oterm" in res
