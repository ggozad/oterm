import json

import pytest

from oterm.ollamaclient import OllamaLLM
from oterm.tools.location import LocationTool, get_current_location


@pytest.mark.asyncio
async def test_location_tool():
    llm = OllamaLLM(
        model="mistral-nemo",
        tool_defs=[
            {"tool": LocationTool, "callable": get_current_location},
        ],
    )
    res = await llm.completion(
        "In which city am I currently located?. Reply with no other text, just the city."
    )
    current_location = json.loads(await get_current_location()).get("city")
    assert current_location in res
