from pathlib import Path

import pytest
from mcp import StdioServerParameters

from oterm.ollamaclient import OllamaLLM
from oterm.tools import MCPClient, MCPToolCallable
from oterm.types import Tool

mcp_server_executable = Path(__file__).parent / "mcp_servers.py"

server_config = {
    "oracle": {
        "command": "mcp",
        "args": ["run", str(mcp_server_executable.absolute())],
    }
}


@pytest.mark.asyncio
async def test_mcp():

    client = MCPClient(
        "oracle",
        StdioServerParameters.model_validate(server_config["oracle"]),
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
