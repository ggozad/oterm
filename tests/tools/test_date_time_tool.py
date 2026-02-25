from pathlib import Path

import pytest
from pydantic_ai import Tool as PydanticTool

from oterm.agent import get_agent


@pytest.fixture(scope="module")
def vcr_cassette_dir():
    return str(Path(__file__).parent.parent / "cassettes" / "test_date_time_tool")


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_date_time(allow_model_requests, default_model, deterministic_parameters):
    fixed_datetime = "2025-01-15T14:30:45.123456"

    def mock_date_time() -> str:
        """Get the current date and time in ISO format."""
        return fixed_datetime

    tool = PydanticTool(mock_date_time, name="date_time", takes_ctx=False)
    agent = get_agent(
        model=default_model,
        tools=[tool],
        parameters=deterministic_parameters,
    )
    result = await agent.run(
        "What is the time in 24h format? Use the date_time tool to answer this question."
    )

    assert "14:30" in result.output, f"Expected time in response, got: {result.output}"
