import pytest
from mcp import StdioServerParameters

from oterm.tools.mcp import MCPClient


@pytest.mark.asyncio
async def test_mcp_prompts(mcp_server_config):
    client = MCPClient(
        "oracle",
        StdioServerParameters.model_validate(mcp_server_config["oracle"]),
    )
    await client.initialize()
    prompts = await client.get_available_prompts()

    oracle_prompt = prompts[0]
    assert oracle_prompt.name == "Oracle prompt"
    assert oracle_prompt.description == "Prompt to ask the oracle a question."
    args = oracle_prompt.arguments or []
    assert len(args) == 2
    arg_1 = args[0]
    assert arg_1.name == "question"
    assert arg_1.required
    arg_2 = args[1]
    assert arg_2.name == "model"
    assert not arg_2.required

    await client.cleanup()
