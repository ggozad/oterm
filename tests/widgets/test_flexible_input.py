from textual.app import App, ComposeResult
from textual.widgets import Button, Input, TextArea

from oterm.app.widgets.prompt import FlexibleInput


class _Host(App):
    def compose(self) -> ComposeResult:
        yield FlexibleInput("", id="prompt", classes="singleline")


async def test_mount_focuses_input():
    app = _Host()
    async with app.run_test():
        focused = app.focused
        assert isinstance(focused, Input)
        assert focused.id == "promptInput"


async def test_clear_resets_text_and_inputs():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.text = "hello"
        await pilot.pause()
        assert flex.query_one("#promptInput", Input).value == "hello"

        flex.clear()
        await pilot.pause()
        assert flex.text == ""
        assert flex.query_one("#promptInput", Input).value == ""
        assert flex.query_one("#promptArea", TextArea).text == ""


async def test_toggle_multiline_swaps_class():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        assert flex.has_class("singleline")

        flex.toggle_multiline()
        await pilot.pause()
        assert flex.has_class("multiline")
        assert not flex.has_class("singleline")
        assert isinstance(app.focused, TextArea)

        flex.toggle_multiline()
        await pilot.pause()
        assert flex.has_class("singleline")
        assert not flex.has_class("multiline")


async def test_submit_from_input_posts_message():
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

        input_widget = flex.query_one("#promptInput", Input)
        input_widget.value = "hi there"
        await pilot.press("enter")
        await pilot.pause()

        assert received == ["hi there"]


async def test_post_button_submits_current_text():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.text = "ready"
        await pilot.pause()

        received: list[str] = []
        original = flex.post_message

        def record(msg):
            if isinstance(msg, FlexibleInput.Submitted):
                received.append(msg.value)
            return original(msg)

        flex.post_message = record  # ty: ignore[invalid-assignment]
        await flex.on_post()
        await pilot.pause()

        assert received == ["ready"]


async def test_multiline_text_disables_toggle_button():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.text = "line1\nline2"
        await pilot.pause()
        toggle = flex.query_one("#toggle-multiline", Button)
        assert toggle.disabled is True

        flex.text = "oneline"
        await pilot.pause()
        assert toggle.disabled is False


async def test_submit_from_textarea_posts_message():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.toggle_multiline()
        await pilot.pause()

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


async def test_input_changed_updates_flex_text():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        inp = flex.query_one("#promptInput", Input)
        inp.value = "typed here"
        await pilot.pause()
        assert flex.text == "typed here"


async def test_textarea_changed_updates_flex_text():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.toggle_multiline()
        await pilot.pause()

        ta = flex.query_one("#promptArea", TextArea)
        ta.text = "line a\nline b"
        await pilot.pause()
        assert flex.text == "line a\nline b"


async def test_pastable_input_ctrl_m_toggles_multiline():
    """PastableInput exposes ctrl+m to toggle its parent FlexibleInput."""
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        assert flex.has_class("singleline")

        inp = flex.query_one("#promptInput", Input)
        inp.focus()
        await pilot.press("ctrl+m")
        await pilot.pause()
        assert flex.has_class("multiline")


async def test_multiline_paste_switches_to_multiline():
    """Pasting multiple lines in the Input flips FlexibleInput to multiline."""
    from textual.events import Paste

    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        inp = flex.query_one("#promptInput", Input)
        inp.post_message(Paste("first\nsecond"))
        await pilot.pause()
        assert flex.has_class("multiline")


async def test_single_line_paste_stays_singleline():
    from textual.events import Paste

    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        inp = flex.query_one("#promptInput", Input)
        inp.post_message(Paste("just one line"))
        await pilot.pause()
        assert flex.has_class("singleline")


async def test_empty_paste_is_ignored():
    from textual.events import Paste

    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        inp = flex.query_one("#promptInput", Input)
        inp.post_message(Paste(""))
        await pilot.pause()
        assert flex.has_class("singleline")


async def test_focus_delegates_to_visible_input():
    app = _Host()
    async with app.run_test() as pilot:
        flex = app.query_one(FlexibleInput)
        flex.focus()
        await pilot.pause()
        assert isinstance(app.focused, Input)

        flex.toggle_multiline()
        await pilot.pause()
        flex.focus()
        await pilot.pause()
        assert isinstance(app.focused, TextArea)


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

        # Invoke the nested callback directly — simulate the ImageSelect result.
        async def _invoke():
            # Reach into action_add_image's closure: call with stub push_screen.
            received_calls: list = []

            def capture_push(screen, callback):
                received_calls.append((screen, callback))

            flex.app.push_screen = capture_push  # ty: ignore[invalid-assignment]
            flex.action_add_image()
            await pilot.pause()
            _, cb = received_calls[0]
            await cb((Path("/tmp/img.png"), "b64"))
            await cb(None)  # callback with None is a no-op

        await _invoke()
        await pilot.pause()
        assert received == [(Path("/tmp/img.png"), "b64")]
