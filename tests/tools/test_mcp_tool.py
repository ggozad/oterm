import pytest

import os
import sys
from oterm.ollamaclient import OllamaLLM
from oterm.tools import MCPClient, McpToolCallable
from oterm.types import Tool

from mcp import StdioServerParameters

# locate the exmaple MCP server co-located in this directory

mcp_server_dir = os.path.dirname(os.path.abspath(__file__))
mcp_server_file = os.path.join(mcp_server_dir, "example_mcp_server.py")
                           
# mcpServers config in same syntax used by reference MCP

servers_config = {
    "mcpServers": {

        "testMcpServer": {
            "command": "mcp",   # be sure to . .venv/bin/activate so that mcp command is found
            "args": [
                "run",
                mcp_server_file
            ]
        }

    }
}


@pytest.mark.asyncio
async def test_mcp():

    servers = servers_config.get("mcpServers")

    server0 = "testMcpServer"
    config0 = servers[server0]
    
    client = MCPClient(
        StdioServerParameters.model_validate(config0)
    )
    await client.initialize()
    tools = await client.get_available_tools()

    # print(f"TOOLS:{tools}")
    mcp_tool = tools[0]

    # create an Ollama tool referencing the MCP tool in the MCP server
    oterm_tool = Tool(
        function=Tool.Function(
            name=mcp_tool.name,
            description=mcp_tool.description,
            parameters=Tool.Function.Parameters.model_validate(mcp_tool.inputSchema),
            ),
        )

    mcpToolCallable = McpToolCallable(mcp_tool.name, server0, client)

    llm = OllamaLLM(
        tool_defs=[{"tool": oterm_tool, "callable": mcpToolCallable.call}],
    )

    res = await llm.completion(
        "Please call my simple-tool with values 12 and 25."
    )
    
    print(f"COMPLETION:{res}")
    assert "300" in res

    # clients must be destroyed in reverse order
    await client.cleanup()
