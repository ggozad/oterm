from fastmcp.client.logging import LogMessage

from oterm.log import log


async def log_handler(params: LogMessage) -> None:
    if params.level == "error" or params.level == "critical":
        log.error(params.data)
    elif params.level == "warning":
        log.warning(params.data)
    elif params.level == "info":
        log.info(params.data)
    elif params.level == "debug":  # pragma: no branch
        log.debug(params.data)
