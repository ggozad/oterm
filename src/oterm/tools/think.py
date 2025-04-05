from oterm.types import Tool

ThinkTool = Tool(
    type="function",
    function=Tool.Function(
        name="think",
        description="Use the tool to think about something. It will not obtain new information or change the database, but just append the thought to the log. Use it when complex reasoning or some cache memory is needed.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={
                "thought": Tool.Function.Parameters.Property(
                    type="string", description="A thought to think about."
                ),
            },
            required=["thought"],
        ),
    ),
)


async def think(thought: str) -> str:
    return thought
