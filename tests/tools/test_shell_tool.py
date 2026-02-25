from pathlib import Path

import pytest

from oterm.agent import get_agent
from oterm.tools import make_tool_def
from oterm.tools.shell import shell


@pytest.fixture(scope="module")
def vcr_cassette_dir():
    return str(Path(__file__).parent.parent / "cassettes" / "test_shell_tool")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_shell(allow_model_requests, default_model, deterministic_parameters):
    tool_def = make_tool_def(shell)
    agent = get_agent(
        model=default_model,
        tools=[tool_def["tool"]],
        parameters=deterministic_parameters,
    )
    result = await agent.run(
        "What is the current directory? Use the shell tool available and execute the command."
    )
    assert "oterm" in result.output
