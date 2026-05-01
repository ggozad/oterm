from textual.app import App
from textual.widgets import RichLog

from oterm.app.log_viewer import LogViewer


class _Host(App):
    pass


async def test_escape_cancels():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        app.push_screen(LogViewer(), lambda r: received.append(r))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]


async def test_new_log_lines_are_written(monkeypatch):
    import oterm.app.log_viewer as lv
    from oterm.log import LogGroup

    fake_lines = [
        (LogGroup.INFO, "hello"),
        (LogGroup.ERROR, "kaboom"),
    ]
    monkeypatch.setattr(lv, "log_lines", fake_lines)

    app = _Host()
    async with app.run_test() as pilot:
        screen = LogViewer()
        app.push_screen(screen)
        await pilot.pause(0.6)  # let debounce fire

        widget = screen.query_one(RichLog)
        assert screen.line_count == 2
        # RichLog appends lines; just verify it received something.
        assert len(widget.lines) >= 2


async def test_log_viewer_shows_save_hint():
    from textual.widgets import Label

    app = _Host()
    async with app.run_test() as pilot:
        screen = LogViewer()
        app.push_screen(screen)
        await pilot.pause()
        labels = [str(label.content) for label in screen.query(Label)]
        assert any("s" in text and "save" in text.lower() for text in labels), (
            f"expected a hint mentioning 's' and 'save'; got {labels}"
        )


async def test_save_logs_writes_log_file(monkeypatch, tmp_path):
    import oterm.app.log_viewer as lv
    from oterm.log import LogGroup

    fake_lines = [
        (LogGroup.INFO, "hello"),
        (LogGroup.ERROR, "boom"),
    ]
    monkeypatch.setattr(lv, "log_lines", fake_lines)
    monkeypatch.chdir(tmp_path)

    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(LogViewer())
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

    files = list(tmp_path.glob("oterm-logs-*.txt"))
    assert len(files) == 1, f"expected one log file, found {files}"
    assert files[0].read_text(encoding="utf-8") == "[INFO] hello\n[ERROR] boom\n"


async def test_save_logs_emits_notification(monkeypatch, tmp_path):
    import oterm.app.log_viewer as lv
    from oterm.log import LogGroup

    fake_lines = [(LogGroup.INFO, "hi")]
    monkeypatch.setattr(lv, "log_lines", fake_lines)
    monkeypatch.chdir(tmp_path)

    notifications: list[str] = []

    class _NotifyHost(_Host):
        def notify(self, message, *args, **kwargs):
            notifications.append(message)
            return super().notify(message, *args, **kwargs)

    app = _NotifyHost()
    async with app.run_test() as pilot:
        app.push_screen(LogViewer())
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

    assert any("Logs exported to" in n for n in notifications), notifications


async def test_rapid_double_save_creates_two_files(monkeypatch, tmp_path):
    import oterm.app.log_viewer as lv
    from oterm.log import LogGroup

    monkeypatch.setattr(lv, "log_lines", [(LogGroup.INFO, "x")])
    monkeypatch.chdir(tmp_path)

    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(LogViewer())
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

    files = sorted(tmp_path.glob("oterm-logs-*.txt"))
    assert len(files) == 2, f"expected two distinct log files, found {files}"


async def test_save_logs_handles_oserror(monkeypatch, tmp_path):
    import oterm.app.log_viewer as lv
    from oterm.log import LogGroup

    monkeypatch.setattr(lv, "log_lines", [(LogGroup.INFO, "x")])
    monkeypatch.chdir(tmp_path)

    def _raise(*args, **kwargs):
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(lv.Path, "open", _raise)

    notifications: list[tuple[str, dict]] = []

    class _NotifyHost(_Host):
        def notify(self, message, *args, **kwargs):
            notifications.append((message, kwargs))
            return super().notify(message, *args, **kwargs)

    app = _NotifyHost()
    async with app.run_test() as pilot:
        app.push_screen(LogViewer())
        await pilot.pause()
        await pilot.press("s")
        await pilot.pause()

    assert list(tmp_path.glob("oterm-logs-*.txt")) == []
    error_notifs = [
        (msg, kw) for msg, kw in notifications if kw.get("severity") == "error"
    ]
    assert len(error_notifs) == 1, (
        f"expected one error notification, got {notifications}"
    )
    assert "Failed to export" in error_notifs[0][0]
