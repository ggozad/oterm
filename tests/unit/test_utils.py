import asyncio
import sys

import httpx

from oterm.utils import (
    debounce,
    get_default_data_dir,
    int_to_semantic_version,
    parse_response,
    semantic_version_to_int,
    throttle,
)


class TestParseResponse:
    def test_no_think_tag(self):
        parsed = parse_response("plain text")
        assert parsed.thought == ""
        assert parsed.response == "plain text"
        assert parsed.formatted_output == "plain text"

    def test_empty_think_tag(self):
        parsed = parse_response("<think></think>reply")
        assert parsed.thought == ""
        assert parsed.response == "reply"
        assert parsed.formatted_output == "<think></think>reply"

    def test_think_tag_formats_blockquote(self):
        parsed = parse_response("<think>because</think>answer")
        assert parsed.thought == "> because"
        assert parsed.response == "answer"
        assert "<thought" in parsed.formatted_output
        assert "> because" in parsed.formatted_output
        assert parsed.formatted_output.endswith("answer")

    def test_multiline_think_blockquotes_each_line(self):
        parsed = parse_response("<think>a\nb\nc</think>answer")
        assert parsed.thought == "> a\n> b\n> c"

    def test_malformed_think_without_close_is_passthrough(self):
        parsed = parse_response("<think>unclosed")
        assert parsed.thought == ""
        assert parsed.response == "<think>unclosed"


class TestSemanticVersion:
    def test_sqlite_user_version_roundtrip(self):
        assert semantic_version_to_int("0.1.5") == 261
        assert int_to_semantic_version(261) == "0.1.5"

    def test_zero_and_max_values(self):
        assert semantic_version_to_int("0.0.0") == 0
        assert int_to_semantic_version(0) == "0.0.0"
        assert semantic_version_to_int("255.255.255") == 16777215
        assert int_to_semantic_version(16777215) == "255.255.255"


class TestThrottle:
    async def test_first_call_executes_immediately(self):
        count = 0

        @throttle(0.1)
        async def f():
            nonlocal count
            count += 1

        await f()
        assert count == 1

    async def test_blocks_subsequent_calls_within_interval(self):
        count = 0

        @throttle(0.1)
        async def f():
            nonlocal count
            count += 1

        await f()
        await f()
        await f()
        assert count == 1

    async def test_allows_call_after_interval(self):
        count = 0

        @throttle(0.05)
        async def f():
            nonlocal count
            count += 1

        await f()
        await asyncio.sleep(0.06)
        await f()
        assert count == 2

    async def test_args_and_kwargs_forwarded(self):
        seen: list = []

        @throttle(0.1)
        async def f(*args, **kwargs):
            seen.append((args, kwargs))

        await f(1, 2, k="v")
        assert seen == [((1, 2), {"k": "v"})]


class TestDebounce:
    async def test_delays_execution(self):
        count = 0

        @debounce(0.05)
        async def f():
            nonlocal count
            count += 1

        await f()
        assert count == 0
        await asyncio.sleep(0.08)
        assert count == 1

    async def test_cancels_previous_calls(self):
        count = 0

        @debounce(0.05)
        async def f():
            nonlocal count
            count += 1

        await f()
        await asyncio.sleep(0.02)
        await f()
        await asyncio.sleep(0.02)
        await f()
        await asyncio.sleep(0.08)
        assert count == 1

    async def test_args_from_latest_call(self):
        seen: list = []

        @debounce(0.05)
        async def f(*args, **kwargs):
            seen.append((args, kwargs))

        await f(1, key="a")
        await f(2, key="b")
        await asyncio.sleep(0.08)
        assert seen == [((2,), {"key": "b"})]


class TestGetDefaultDataDir:
    def test_darwin_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        path = get_default_data_dir()
        assert str(path).endswith("Library/Application Support/oterm")

    def test_darwin_respects_xdg(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        path = get_default_data_dir()
        assert path == tmp_path / "xdg" / "oterm"

    def test_linux_default(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        path = get_default_data_dir()
        assert str(path).endswith(".local/share/oterm")

    def test_linux_respects_xdg(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        path = get_default_data_dir()
        assert path == tmp_path / "xdg" / "oterm"

    def test_windows(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("HOMEPATH", str(tmp_path))
        path = get_default_data_dir()
        assert str(path).endswith("AppData/Roaming/oterm")


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient driven by a queued response or error."""

    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url):
        if self._error is not None:
            raise self._error
        return self._response


class TestIsUpToDate:
    async def test_up_to_date(self, monkeypatch):
        from importlib import metadata

        from oterm import utils

        current = metadata.version("oterm")
        monkeypatch.setattr(
            utils.httpx,
            "AsyncClient",
            lambda: _FakeAsyncClient(
                _FakeResponse(200, {"info": {"version": current}})
            ),
        )
        up, running, latest = await utils.is_up_to_date()
        assert up is True
        assert str(running) == current
        assert str(latest) == current

    async def test_outdated(self, monkeypatch):
        from oterm import utils

        monkeypatch.setattr(
            utils.httpx,
            "AsyncClient",
            lambda: _FakeAsyncClient(
                _FakeResponse(200, {"info": {"version": "9999.0.0"}})
            ),
        )
        up, _, latest = await utils.is_up_to_date()
        assert up is False
        assert str(latest) == "9999.0.0"

    async def test_network_error_treated_as_up_to_date(self, monkeypatch):
        from oterm import utils

        monkeypatch.setattr(
            utils.httpx,
            "AsyncClient",
            lambda: _FakeAsyncClient(error=httpx.ConnectError("boom")),
        )
        up, running, latest = await utils.is_up_to_date()
        assert up is True
        assert running == latest


class TestCheckOllama:
    async def test_reachable(self, monkeypatch):
        from oterm import utils

        monkeypatch.setattr(
            utils.httpx,
            "AsyncClient",
            lambda: _FakeAsyncClient(_FakeResponse(200)),
        )
        assert await utils.check_ollama() is True

    async def test_unreachable_http_error(self, monkeypatch):
        from oterm import utils

        monkeypatch.setattr(
            utils.httpx,
            "AsyncClient",
            lambda: _FakeAsyncClient(error=httpx.ConnectError("nope")),
        )

        # Stub out app.notify and the scheduled quit task so the test doesn't
        # import the full TUI or actually exit.
        class _StubApp:
            def notify(self, *args, **kwargs):
                pass

        class _StubModule:
            app = _StubApp()

        monkeypatch.setitem(sys.modules, "oterm.app.oterm", _StubModule())
        monkeypatch.setattr(
            utils.asyncio, "create_task", lambda coro: coro.close() or None
        )

        assert await utils.check_ollama() is False

    async def test_non_200_treated_as_down(self, monkeypatch):
        from oterm import utils

        monkeypatch.setattr(
            utils.httpx,
            "AsyncClient",
            lambda: _FakeAsyncClient(_FakeResponse(500)),
        )

        class _StubApp:
            def notify(self, *args, **kwargs):
                pass

        class _StubModule:
            app = _StubApp()

        monkeypatch.setitem(sys.modules, "oterm.app.oterm", _StubModule())
        monkeypatch.setattr(
            utils.asyncio, "create_task", lambda coro: coro.close() or None
        )

        assert await utils.check_ollama() is False
