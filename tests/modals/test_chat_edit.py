import json

import pytest
from textual.app import App
from textual.widgets import Button, Checkbox, Input, TextArea

from oterm.app.chat_edit import ChatEdit
from oterm.app.widgets.model_select import ModelSelect
from oterm.types import ChatModel


@pytest.fixture(autouse=True)
def stub_providers(monkeypatch):
    """Keep ChatEdit.on_mount from actually calling Ollama or any SDK."""
    from oterm.providers import ollama as ollama_mod

    class _M:
        model = "llama3"

        def __getitem__(self, key):
            return 1_000_000_000 if key == "size" else None

    class _Resp:
        models = [_M()]

    monkeypatch.setattr(ollama_mod, "list_models", lambda: _Resp())

    class _Show(dict):
        @property
        def parameters(self):
            return ""

    monkeypatch.setattr(ollama_mod, "show_model", lambda m: _Show())
    return _Resp


class _Host(App):
    pass


async def test_compose_renders_core_widgets(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(ChatEdit())
        await pilot.pause()
        screen = app.screen
        assert screen.query_one(ModelSelect)
        assert screen.query_one(".system", TextArea)
        assert screen.query_one("#temperature-input", Input)
        assert screen.query_one("#top-p-input", Input)
        assert screen.query_one("#max-tokens-input", Input)
        assert screen.query_one("#thinking-checkbox", Checkbox)
        assert screen.query_one("#save-btn", Button)


async def test_escape_dismisses_with_none(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        app.push_screen(ChatEdit(), lambda r: received.append(r))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert received == [None]


async def test_save_dismisses_with_chat_model_json(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        screen.query_one("#temperature-input", Input).value = "0.5"
        screen.query_one("#top-p-input", Input).value = ""
        screen.query_one("#max-tokens-input", Input).value = ""
        await pilot.pause()

        screen._return_chat_meta()
        await pilot.pause()

        assert received and received[0]
        payload = json.loads(received[0])
        assert payload["model"] == "llama3"
        assert payload["parameters"]["temperature"] == 0.5


async def test_missing_model_notifies_and_does_not_dismiss(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = ChatEdit()
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        screen.query_one(ModelSelect).set_value("")
        await pilot.pause()

        screen._return_chat_meta()
        await pilot.pause()

        assert received == []
        assert any("model name" in n.message.lower() for n in list(app._notifications))


@pytest.mark.parametrize(
    "field,value,message_fragment",
    [
        ("#temperature-input", "nope", "Invalid temperature"),
        ("#temperature-input", "3.0", "Temperature must be"),
        ("#top-p-input", "nope", "Invalid Top P"),
        ("#top-p-input", "2.0", "Top P must be"),
        ("#max-tokens-input", "nope", "Invalid Max Tokens"),
        ("#max-tokens-input", "-1", "Max Tokens must be"),
    ],
)
async def test_parameter_validation_errors(app_config, field, value, message_fragment):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        screen.query_one(field, Input).value = value
        await pilot.pause()

        screen._return_chat_meta()
        await pilot.pause()

        assert received == []
        assert any(
            message_fragment.lower() in n.message.lower()
            for n in list(app._notifications)
        )
