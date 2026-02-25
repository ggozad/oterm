from pathlib import Path

import pytest

from oterm.agent import get_agent
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.tools import MCPToolCallable, mcp_tool_to_pydantic_tool


@pytest.fixture(scope="module")
def vcr_cassette_dir():
    return str(Path(__file__).parent.parent / "cassettes" / "test_mcp_sampling")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_mcp_sampling(
    allow_model_requests,
    mcp_client: MCPClient,
    default_model,
    deterministic_parameters,
):
    """
    Test the sampling capbilities of oterm.
    Here we go full circle and use the MCP client to call the server
    to call the client again with a sampling request.
    """

    tools = await mcp_client.get_available_tools()
    puzzle_solver = tools[1]
    mcpToolCallable = MCPToolCallable(puzzle_solver.name, "test_server", mcp_client)
    pydantic_tool = mcp_tool_to_pydantic_tool(puzzle_solver, mcpToolCallable)

    agent = get_agent(
        model=default_model,
        tools=[pydantic_tool],
        parameters=deterministic_parameters,
    )

    result = await agent.run(
        """Use the puzzle_solver tool to solve this puzzle:
        Jack is looking at Anne. Anne is looking at George.
        Jack is married, George is not, and we don't know if Anne is married.
        Is a married person looking at an unmarried person?"""
    )
    assert "no" in result.output.lower() or "yes" in result.output.lower()
