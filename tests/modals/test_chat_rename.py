from textual.app import App
from textual.widgets import Input

from oterm.app.chat_rename import ChatRename


class _Host(App):
    pass


async def test_initial_value_is_old_name():
    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatRename("old name")
        app.push_screen(screen)
        await pilot.pause()
        assert screen.query_one("#chat-name-input", Input).value == "old name"


async def test_submit_dismisses_with_new_name():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = ChatRename("old")
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        inp = screen.query_one("#chat-name-input", Input)
        inp.value = "fresh"
        await pilot.press("enter")
        await pilot.pause()
        assert received == ["fresh"]


async def test_empty_submit_is_ignored():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = ChatRename("old")
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        inp = screen.query_one("#chat-name-input", Input)
        inp.value = ""
        await pilot.press("enter")
        await pilot.pause()
        assert received == []


async def test_escape_cancels_with_none():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        app.push_screen(ChatRename("old"), lambda r: received.append(r))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]
