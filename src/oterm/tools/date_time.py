from datetime import datetime

from oterm.tools import Parameters, Tool, ToolFunction

DateTimeTool = Tool(
    type="function",
    function=ToolFunction(
        name="date_time",
        description="Function to get the current date and time",
        parameters=Parameters(
            type="object",
            properties={},
            required=[],
        ),
    ),
)


def date_time() -> str:
    return datetime.now().isoformat()
