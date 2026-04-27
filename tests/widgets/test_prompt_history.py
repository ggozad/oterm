from textual.app import App
from textual.widgets import OptionList

from oterm.app.prompt_history import PromptHistory


class _Host(App):
    pass


async def test_history_populates_option_list():
    app = _Host()
    async with app.run_test() as pilot:
        screen = PromptHistory(["first", "second", "third"])
        app.push_screen(screen)
        await pilot.pause()

        option_list = screen.query_one("#prompt-history", OptionList)
        assert option_list.option_count == 3


async def test_selection_dismisses_with_chosen_prompt():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []

        screen = PromptHistory(["alpha", "beta"])
        app.push_screen(screen, lambda result: received.append(result))
        await pilot.pause()

        option_list = screen.query_one("#prompt-history", OptionList)
        option_list.highlighted = 1
        await pilot.press("enter")
        await pilot.pause()

        assert received == ["beta"]


async def test_escape_cancels_with_none():
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []

        app.push_screen(
            PromptHistory(["only"]),
            lambda result: received.append(result),
        )
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert received == [None]
