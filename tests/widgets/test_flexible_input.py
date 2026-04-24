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
