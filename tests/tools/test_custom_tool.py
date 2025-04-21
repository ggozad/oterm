import pytest

from oterm.tools.date_time import DateTimeTool, date_time
from oterm.tools.external import load_external_tools


@pytest.mark.asyncio
async def test_loading_custom_tool():
    # Test loading a callable from a well-defined module
    tools = load_external_tools(
        [
            {
                "tool": "oterm.tools.date_time:DateTimeTool",
                "callable": "oterm.tools.date_time:date_time",
            }
        ]
    )

    assert len(tools) == 1
    assert tools[0]["tool"] == DateTimeTool
    assert tools[0]["callable"] == date_time
