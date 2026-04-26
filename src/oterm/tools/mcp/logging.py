from mcp.client.session import LoggingFnT
from mcp.types import LoggingMessageNotificationParams

from oterm.log import log


class Logger(LoggingFnT):
    async def __call__(self, params: LoggingMessageNotificationParams) -> None:
        if params.level == "error" or params.level == "critical":
            log.error(params.data)
        elif params.level == "warning":
            log.warning(params.data)
        elif params.level == "info":
            log.info(params.data)
        elif params.level == "debug":  # pragma: no branch
            log.debug(params.data)
