import json

import pytest
from mcp.types import Prompt, PromptArgument
from textual.app import App
from textual.widgets import Button, Input, OptionList

from oterm.app.mcp_prompt import MCPPrompt


class _Host(App):
    pass


@pytest.fixture
def fake_prompts(monkeypatch):
    """Install a fake MCP prompt registry so MCPPrompt has content."""
    import oterm.tools.mcp.prompts as prompts_mod

    argless = Prompt(
        name="argless",
        description="No arguments",
        arguments=[],
    )
    required = Prompt(
        name="required",
        description="Needs arg",
        arguments=[PromptArgument(name="q", required=True)],
    )

    async def argless_call(**kwargs):
        from mcp.types import PromptMessage, TextContent

        return [PromptMessage(role="user", content=TextContent(type="text", text="hi"))]

    async def required_call(**kwargs):
        from mcp.types import PromptMessage, TextContent

        text = f"asked: {kwargs.get('q', '')}"
        return [PromptMessage(role="user", content=TextContent(type="text", text=text))]

    registry = {
        "server": [
            {"prompt": argless, "callable": argless_call},
            {"prompt": required, "callable": required_call},
        ]
    }
    monkeypatch.setattr(prompts_mod, "available_prompt_defs", registry)
    monkeypatch.setattr("oterm.app.mcp_prompt.available_prompt_defs", registry)

    def flat():
        import itertools

        return list(itertools.chain.from_iterable(registry.values()))

    monkeypatch.setattr("oterm.app.mcp_prompt.available_prompt_calls", flat)
    return registry


async def test_option_list_populated(fake_prompts):
    app = _Host()
    async with app.run_test() as pilot:
        screen = MCPPrompt()
        app.push_screen(screen)
        await pilot.pause()

        option_list = screen.query_one("#mcp-prompt-select", OptionList)
        assert option_list.option_count == 2


async def test_escape_cancels(fake_prompts):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        app.push_screen(MCPPrompt(), lambda r: received.append(r))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]


async def test_argless_prompt_enables_submit_and_returns_messages(fake_prompts):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = MCPPrompt()
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        option_list = screen.query_one("#mcp-prompt-select", OptionList)
        option_list.highlighted = 0  # argless
        # Debounce on on_text_area_change is 1.0s — wait it out so messages populate
        await pilot.pause(1.2)

        submit = screen.query_one("#submit", Button)
        assert submit.disabled is False

        screen.on_button_pressed(Button.Pressed(submit))
        await pilot.pause()

        assert received and received[0] is not None
        messages = json.loads(received[0])
        assert messages == [{"role": "user", "content": "hi"}]


async def test_prompt_option_widget_renders_name_and_description(fake_prompts):
    from oterm.app.mcp_prompt import PromptOptionWidget

    app = _Host()
    async with app.run_test():
        prompt = fake_prompts["server"][0]["prompt"]
        widget = PromptOptionWidget("server", prompt)
        text = str(widget.render())
        assert "server" in text
        assert prompt.name in text


async def test_cancel_button_dismisses(fake_prompts):
    from textual.widgets import Button

    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = MCPPrompt()
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        cancel_btn = next(b for b in screen.query(Button) if b.name == "cancel")
        screen.on_button_pressed(Button.Pressed(cancel_btn))
        await pilot.pause()
        assert received == [None]


async def test_required_prompt_initially_disables_submit(fake_prompts):
    app = _Host()
    async with app.run_test() as pilot:
        screen = MCPPrompt()
        app.push_screen(screen)
        await pilot.pause()

        option_list = screen.query_one("#mcp-prompt-select", OptionList)
        option_list.highlighted = 1  # required
        await pilot.pause()

        submit = screen.query_one("#submit", Button)
        assert submit.disabled is True

        # Providing a value for the required arg should enable submit after debounce
        form_input = screen.query_one("#arg-q", Input)
        form_input.value = "why"
        await pilot.pause(1.2)
        assert submit.disabled is False
