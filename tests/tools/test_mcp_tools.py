import pytest
from mcp import StdioServerParameters

from oterm.ollamaclient import OllamaLLM
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.tools import MCPToolCallable
from oterm.types import Tool


@pytest.mark.asyncio
async def test_mcp(mcp_server_config):
    client = MCPClient(
        "oracle", StdioServerParameters.model_validate(mcp_server_config["oracle"])
    )
    await client.initialize()
    tools = await client.get_available_tools()

    tool = tools[0]
    oterm_tool = Tool(
        function=Tool.Function(
            name=tool.name,
            description=tool.description,
            parameters=Tool.Function.Parameters.model_validate(tool.inputSchema),
        ),
    )

    mcpToolCallable = MCPToolCallable(tool.name, "oracle", client)
    llm = OllamaLLM(
        tool_defs=[{"tool": oterm_tool, "callable": mcpToolCallable.call}],
    )

    res = await llm.completion("Ask the oracle what is the best client for Ollama.")
    assert "oterm" in res
    await client.cleanup()
