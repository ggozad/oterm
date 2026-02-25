from pathlib import Path

import pytest
from mcp.types import Tool as MCPTool

from oterm.agent import get_agent
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.tools import MCPToolCallable, mcp_tool_to_pydantic_tool


@pytest.fixture(scope="module")
def vcr_cassette_dir():
    return str(Path(__file__).parent.parent / "cassettes" / "test_mcp_tools")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_mcp_tools(
    allow_model_requests, mcp_client: MCPClient, default_model, deterministic_parameters
):
    tools = await mcp_client.get_available_tools()
    for oracle in tools:
        assert MCPTool.model_validate(oracle)

    oracle = tools[0]

    mcpToolCallable = MCPToolCallable(oracle.name, "test_server", mcp_client)
    pydantic_tool = mcp_tool_to_pydantic_tool(oracle, mcpToolCallable)

    agent = get_agent(
        model=default_model,
        tools=[pydantic_tool],
        parameters=deterministic_parameters,
    )

    result = await agent.run("Ask the oracle what is the best client for Ollama.")
    res = result.output.lower()
    assert any(
        [
            "oterm" in res,
            "oter" in res,
            "orterm" in res,
        ]
    )
