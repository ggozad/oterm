import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.date_time import DateTimeTool


@pytest.mark.asyncio
async def test_date_time(default_model, deterministic_options):
    fixed_datetime = "2025-01-15T14:30:45.123456"

    def mock_date_time() -> str:
        return fixed_datetime

    llm = OllamaLLM(
        model=default_model,
        tool_defs=[{"tool": DateTimeTool, "callable": mock_date_time}],
        options=deterministic_options,
    )
    res = ""
    async for _, text in llm.stream(
        "What is the time in 24h format? Use the date_time tool to answer this question."
    ):
        res = text

    assert "14:30" in res, f"Expected time in response, got: {res}"
