from textual.app import App, ComposeResult
from textual.widgets import TextArea

from oterm.app.widgets.prompt import FlexibleInput


class _Host(App):
    def compose(self) -> ComposeResult:
        yield FlexibleInput("", id="prompt")


async def test_mount_focuses_textarea():
    app = _Host()
    async with app.run_test():
        focused = app.focused
        assert isinstance(focused, TextArea)
        assert focused.id == "promptArea"


async def test_clear_resets_text_and_textarea():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.text = "hello"
        await pilot.pause()
        assert flex.query_one("#promptArea", TextArea).text == "hello"

        flex.clear()
        await pilot.pause()
        assert flex.text == ""
        assert flex.query_one("#promptArea", TextArea).text == ""


async def test_submit_from_textarea_posts_message():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        received: list[str] = []
        original = flex.post_message

        def record(msg):
            if isinstance(msg, FlexibleInput.Submitted):
                received.append(msg.value)
            return original(msg)

        flex.post_message = record  # ty: ignore[invalid-assignment]

        ta = flex.query_one("#promptArea", TextArea)
        ta.text = "multi-line body"
        await pilot.press("enter")
        await pilot.pause()

        assert received == ["multi-line body"]


async def test_textarea_changed_updates_flex_text():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        ta = flex.query_one("#promptArea", TextArea)
        ta.text = "line a\nline b"
        await pilot.pause()
        assert flex.text == "line a\nline b"


async def test_focus_delegates_to_textarea():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.focus()
        await pilot.pause()
        assert isinstance(app.focused, TextArea)


async def test_shift_enter_inserts_newline():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        ta = flex.query_one("#promptArea", TextArea)
        ta.text = "first"
        ta.cursor_location = (0, 5)
        await pilot.press("shift+enter")
        await pilot.pause()
        assert ta.text == "first\n"


async def test_add_image_action_pushes_image_select_screen(monkeypatch):
    from oterm.app.image_browser import ImageSelect

    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.action_add_image()
        await pilot.pause()
        assert isinstance(app.screen, ImageSelect)


async def test_add_image_callback_posts_image_added_message():
    """When the image screen returns a (path, b64), FlexibleInput posts ImageAdded."""
    from pathlib import Path

    from oterm.app.widgets.image import ImageAdded

    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        received: list = []
        original = flex.post_message

        def record(msg):
            if isinstance(msg, ImageAdded):
                received.append((msg.path, msg.image))
            return original(msg)

        flex.post_message = record  # ty: ignore[invalid-assignment]

        received_calls: list = []

        def capture_push(screen, callback):
            received_calls.append((screen, callback))

        flex.app.push_screen = capture_push  # ty: ignore[invalid-assignment]
        flex.action_add_image()
        await pilot.pause()
        _, cb = received_calls[0]
        await cb((Path("/tmp/img.png"), "b64"))
        await cb(None)  # callback with None is a no-op
        await pilot.pause()

        assert received == [(Path("/tmp/img.png"), "b64")]
