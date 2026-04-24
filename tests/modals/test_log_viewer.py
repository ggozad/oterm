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
