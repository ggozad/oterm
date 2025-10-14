import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.mcp.client import MCPClient
from oterm.tools.mcp.tools import MCPToolCallable
from oterm.types import Tool


@pytest.mark.asyncio
async def test_mcp_sampling(mcp_client: MCPClient, default_model, deterministic_options):
    """
    Test the sampling capbilities of oterm.
    Here we go full circle and use the MCP client to call the server
    to call the client again with a sampling request.
    """

    tools = await mcp_client.get_available_tools()
    puzzle_solver = tools[1]
    oterm_tool = Tool(
        function=Tool.Function(
            name=puzzle_solver.name,
            description=puzzle_solver.description,
            parameters=Tool.Function.Parameters.model_validate(
                puzzle_solver.inputSchema
            ),
        ),
    )
    mcpToolCallable = MCPToolCallable(puzzle_solver.name, "test_server", mcp_client)
    llm = OllamaLLM(
        model=default_model,
        tool_defs=[{"tool": oterm_tool, "callable": mcpToolCallable.call}],
        options=deterministic_options,
    )

    res = ""
    async for _, text in llm.stream(
        """Use the puzzle_solver tool to solve this puzzle:
        Jack is looking at Anne. Anne is looking at George.
        Jack is married, George is not, and we don't know if Anne is married.
        Is a married person looking at an unmarried person?"""
    ):
        res = text
    assert "no" in res.lower() or "yes" in res.lower()
