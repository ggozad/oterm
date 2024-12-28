from datetime import datetime

from oterm.types import Tool

DateTimeTool = Tool(
    type="function",
    function=Tool.Function(
        name="date_time",
        description="Function to get the current date and time",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={},
            required=[],
        ),
    ),
)


def date_time() -> str:
    return datetime.now().isoformat()
