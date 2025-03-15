from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP("Oracle")


@mcp.resource("config://app")
def get_config() -> str:
    return "Oracle MCP server"


@mcp.tool()
async def oracle(query: str, ctx: Context) -> str:
    return "Oracle says: oterm"


@mcp.prompt(name="Oracle prompt", description="Prompt to ask the oracle a question.")
async def oracle_prompt(question: str, model=None) -> str:
    return f"Ask the oracle the following question: {question}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
