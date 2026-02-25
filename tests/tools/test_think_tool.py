from pathlib import Path

import pytest

from oterm.agent import get_agent
from oterm.tools import make_tool_def
from oterm.tools.think import think


@pytest.fixture(scope="module")
def vcr_cassette_dir():
    return str(Path(__file__).parent.parent / "cassettes" / "test_think_tool")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_think(allow_model_requests, default_model, deterministic_parameters):
    tool_def = make_tool_def(think)
    agent = get_agent(
        model=default_model,
        tools=[tool_def["tool"]],
        parameters=deterministic_parameters,
    )
    result = await agent.run(
        "Use the think tool to reason step by step: what is 17 * 23? "
        "Reply with just the number."
    )
    assert "391" in result.output
