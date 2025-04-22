from mcp import SamplingMessage
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.prompts.base import AssistantMessage, Message, UserMessage
from mcp.types import ModelHint, ModelPreferences, TextContent

mcp = FastMCP("TestServer", port=8080)


@mcp.resource("config://app")
def get_config() -> str:
    return "Oracle MCP server"


@mcp.tool(name="oracle", description="Ask the oracle a question.")
async def oracle(query: str, ctx: Context) -> str:
    return "Oracle says: oterm"


@mcp.tool(name="puzzle_solver", description="Solves a puzzle by asking an advanced AI.")
async def puzzle_solver(puzzle_description: str, ctx: Context) -> str:
    """
    This tool is included to make a sampling request to the server.
    It takes a puzzle description and returns the answer.
    """
    session = ctx.session
    sampling_response = await session.create_message(
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    text=f"Please solve this puzzle: {puzzle_description}", type="text"
                ),
            )
        ],
        model_preferences=ModelPreferences(
            hints=[ModelHint(name="mistral")],
        ),
        max_tokens=100,
    )
    return sampling_response.content.text  # type: ignore


@mcp.prompt(name="oracle_prompt", description="Prompt to ask the oracle a question.")
async def oracle_prompt(question: str) -> str:
    return f"Oracle: {question}"


@mcp.prompt(name="debug_error", description="Prompt to debug an error.")
async def debug_error(error: str, language: str = "python") -> list[Message]:
    return [
        UserMessage(f"I'm seeing this {language} error: {error}"),
        AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")
