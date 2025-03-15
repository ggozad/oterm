from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP("Oracle")


@mcp.resource("config://app")
def get_config() -> str:
    return "Oracle MCP server"


@mcp.tool()
async def oracle(query: str, ctx: Context) -> str:
    return "Oracle says: oterm"
