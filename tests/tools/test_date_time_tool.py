from datetime import datetime

import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.date_time import DateTimeTool, date_time


@pytest.mark.asyncio
async def test_date_time():
    llm = OllamaLLM(
        model="mistral-nemo", tool_defs=[{"tool": DateTimeTool, "callable": date_time}]
    )
    res = await llm.completion(
        "What is the current date in YYYY-MM-DD format?. Reply with no other text, just the date."
    )
    date = datetime.date(datetime.now())
    assert f"{date.year}-{date.month:02d}-{date.day:02d}" in res
