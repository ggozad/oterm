from textual.app import App, ComposeResult
from textual.widgets import Label

from oterm.app.widgets.caps import Capabilities


class _Host(App):
    def compose(self) -> ComposeResult:
        yield Capabilities(id="caps")


async def test_initial_caps_render_as_emoji_labels():
    app = _Host()
    async with app.run_test() as pilot:
        caps = app.query_one(Capabilities)
        caps.caps = ["tools", "vision", "thinking"]  # ty: ignore[invalid-assignment]
        await pilot.pause()

        texts = {str(label.content) for label in caps.query(Label)}
        assert {"🛠️", "👁️", "🧠"}.issubset(texts)


async def test_caps_update_replaces_previous_labels():
    app = _Host()
    async with app.run_test() as pilot:
        caps = app.query_one(Capabilities)
        caps.caps = ["tools", "vision"]  # ty: ignore[invalid-assignment]
        await pilot.pause()
        assert len(list(caps.query(Label))) == 2

        caps.caps = ["thinking"]  # ty: ignore[invalid-assignment]
        await pilot.pause()
        labels = list(caps.query(Label))
        assert len(labels) == 1
        assert str(labels[0].content) == "🧠"


async def test_empty_caps_renders_no_labels():
    app = _Host()
    async with app.run_test() as pilot:
        caps = app.query_one(Capabilities)
        caps.caps = []
        await pilot.pause()
        assert list(caps.query(Label)) == []


async def test_tooltip_is_the_capability_name():
    app = _Host()
    async with app.run_test() as pilot:
        caps = app.query_one(Capabilities)
        caps.caps = ["tools"]  # ty: ignore[invalid-assignment]
        await pilot.pause()
        label = list(caps.query(Label))[0]
        assert label.tooltip == "tools"
