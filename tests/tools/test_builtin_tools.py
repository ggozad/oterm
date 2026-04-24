from datetime import datetime

from oterm.tools.date_time import date_time
from oterm.tools.shell import shell
from oterm.tools.think import think


class TestDateTime:
    def test_returns_iso_string_close_to_now(self):
        parsed = datetime.fromisoformat(date_time())
        assert abs((datetime.now() - parsed).total_seconds()) < 5


class TestShell:
    def test_executes_command_and_returns_stdout(self):
        result = shell("echo hello-oterm")
        assert "hello-oterm" in result

    def test_returns_stdout_not_stderr(self):
        result = shell("echo out; echo err 1>&2")
        assert "out" in result
        assert "err" not in result

    def test_decodes_invalid_utf8_without_raising(self):
        result = shell("printf '\\xff'")
        assert isinstance(result, str)


class TestThink:
    async def test_echoes_the_thought(self):
        assert await think("reasoning") == "reasoning"

    async def test_returns_empty_for_empty_input(self):
        assert await think("") == ""
