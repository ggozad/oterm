from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP("MCP EXAMPLE SERVER")


@mcp.resource("config://app")
def get_config() -> str:
    """Static configuration data"""
    return "Tom5 Server 2024-02-25"


@mcp.tool()
async def simple_tool(x: float, y: float, ctx: Context) -> str:
    await ctx.report_progress(1, 2)
    return str(x * y)
