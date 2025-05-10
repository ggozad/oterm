from datetime import datetime

import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.date_time import DateTimeTool, date_time


@pytest.mark.asyncio
async def test_date_time(default_model):
    llm = OllamaLLM(
        model=default_model, tool_defs=[{"tool": DateTimeTool, "callable": date_time}]
    )
    res = await llm.completion(
        "What is the time in 24h format? Use the date_time tool to answer this question."
    )
    time = datetime.time(datetime.now())
    assert f"{time.hour:02}:{time.minute:02}" in res
