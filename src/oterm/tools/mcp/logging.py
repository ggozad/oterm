from mcp.client.session import LoggingFnT
from mcp.types import LoggingMessageNotificationParams

from oterm.log import log


# This is here to log the messages from the MCP server, when
# there is an upstream fix for https://github.com/modelcontextprotocol/python-sdk/issues/341
class Logger(LoggingFnT):
    async def __call__(self, params: LoggingMessageNotificationParams) -> None:
        if params.level == "error" or params.level == "critical":
            log.error(params.data)
        elif params.level == "warning":
            log.warning(params.data)
        elif params.level == "info":
            log.info(params.data)
        elif params.level == "debug":
            log.debug(params.data)
