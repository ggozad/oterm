import logging

import rich.repr
from textual import Logger, LogGroup

log_lines: list[tuple[LogGroup, str]] = []


def suppress_logging() -> None:
    """Drop the root logger's handlers and raise its level to ERROR.

    Third-party warnings and below are discarded. Errors still reach stderr
    through `logging.lastResort`.
    """
    root = logging.getLogger()
    for hdlr in root.handlers[:]:
        root.removeHandler(hdlr)
    root.setLevel(logging.ERROR)


@rich.repr.auto
class OtermLogger(Logger):
    @property
    def debug(self) -> "OtermLogger":
        """Logs debug messages."""
        return OtermLogger(self._log, LogGroup.DEBUG)

    @property
    def info(self) -> "OtermLogger":
        """Logs information."""
        return OtermLogger(self._log, LogGroup.INFO)

    @property
    def warning(self) -> "OtermLogger":
        """Logs warnings."""
        return OtermLogger(self._log, LogGroup.WARNING)

    @property
    def error(self) -> "OtermLogger":
        """Logs errors."""
        return OtermLogger(self._log, LogGroup.ERROR)

    def __call__(self, *args: object, **kwargs) -> None:
        output = " ".join(str(arg) for arg in args)
        if kwargs:
            key_values = " ".join(f"{key}={value!r}" for key, value in kwargs.items())
            output = f"{output} {key_values}" if output else key_values
        log_lines.append((self._group, output))
        super().__call__(*args, **kwargs)


log = OtermLogger(None)
