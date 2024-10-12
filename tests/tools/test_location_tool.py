import json

import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.location import LocationTool, current_location


@pytest.mark.asyncio
async def test_location_tool():
    llm = OllamaLLM(
        model="mistral-nemo",
        tool_defs=[
            {"tool": LocationTool, "callable": current_location},
        ],
    )
    res = await llm.completion(
        "In which city am I currently located?. Reply with no other text, just the city."
    )
    curr_loc = json.loads(await current_location()).get("city")
    assert curr_loc in res
