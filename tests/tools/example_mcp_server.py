#
# Small Demo server using FastMCP and illustrating debugging and notification streams
#

import logging
from mcp.server.fastmcp import FastMCP, Context
import time
import asyncio

mcp = FastMCP("MCP EXAMPLE SERVER", debug=True, log_level="DEBUG")

logger = logging.getLogger(__name__)

logger.debug(f"MCP STARTING EXAMPLE SERVER")

@mcp.resource("config://app")
def get_config() -> str:
    """Static configuration data"""
    return "Tom5 Server 2024-02-25"

@mcp.tool()
async def simple_tool(x:float, y:float, ctx:Context) -> str:
    logger.debug("IN SIMPLE_TOOL")
    ctx.report_progress(1, 2)
    return x*y

