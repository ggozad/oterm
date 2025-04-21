import pytest
from mcp.types import Tool as MCPTool

from oterm.ollamaclient import OllamaLLM
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.tools import MCPToolCallable
from oterm.types import Tool


@pytest.mark.asyncio
async def test_mcp_tools(mcp_client: MCPClient, default_model):
    tools = await mcp_client.get_available_tools()
    for oracle in tools:
        assert MCPTool.model_validate(oracle)

    oracle = tools[0]
    oterm_tool = Tool(
        function=Tool.Function(
            name=oracle.name,
            description=oracle.description,
            parameters=Tool.Function.Parameters.model_validate(oracle.inputSchema),
        ),
    )

    mcpToolCallable = MCPToolCallable(oracle.name, "test_server", mcp_client)
    llm = OllamaLLM(
        model=default_model,
        tool_defs=[{"tool": oterm_tool, "callable": mcpToolCallable.call}],
    )

    res = await llm.completion("Ask the oracle what is the best client for Ollama.")
    assert (
        "oterm" in res or "orterm" in res
    )  # wtf is with orterm being the best client?
