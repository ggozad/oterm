import rich.repr
from textual import Logger, LogGroup  # type: ignore

log_lines: list[tuple[LogGroup, str]] = []


@rich.repr.auto
class OtermLogger(Logger):
    @property
    def debug(self) -> "OtermLogger":
        """Logs debug messages."""
        return OtermLogger(self._log, LogGroup.DEBUG)

    @property
    def info(self) -> "OtermLogger":
        """Logs information."""
        res = OtermLogger(self._log, LogGroup.INFO)
        return res

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
