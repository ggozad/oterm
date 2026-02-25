import pytest

from oterm.tools.external import load_external_tools


@pytest.mark.asyncio
async def test_loading_custom_tool():
    tools = load_external_tools(
        [
            {
                "callable": "oterm.tools.date_time:date_time",
            }
        ]
    )

    assert len(tools) == 1
    assert tools[0]["name"] == "date_time"
    assert tools[0]["description"] != ""
