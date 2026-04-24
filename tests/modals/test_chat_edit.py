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


async def test_valid_parameters_are_persisted(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        screen.query_one("#temperature-input", Input).value = "0.3"
        screen.query_one("#top-p-input", Input).value = "0.9"
        screen.query_one("#max-tokens-input", Input).value = "512"
        await pilot.pause()

        screen._return_chat_meta()
        await pilot.pause()

        assert received and received[0]
        payload = json.loads(received[0])
        assert payload["parameters"] == {
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 512,
        }


async def test_save_button_triggers_return(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        save_btn = screen.query_one("#save-btn", Button)
        screen.on_button_pressed(Button.Pressed(save_btn))
        await pilot.pause()
        assert received and received[0]


async def test_cancel_button_dismisses_with_none(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        screen = ChatEdit()
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        cancel_btn = next(b for b in screen.query(Button) if b.name == "cancel")
        screen.on_button_pressed(Button.Pressed(cancel_btn))
        await pilot.pause()
        assert received == [None]


async def test_save_action_triggers_return(app_config):
    app = _Host()
    async with app.run_test() as pilot:
        received: list[str | None] = []
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen, lambda r: received.append(r))
        await pilot.pause()

        screen.action_save()
        await pilot.pause()
        assert received and received[0]


async def test_loading_a_model_populates_inputs(app_config, monkeypatch):
    """Selecting a model via ModelSelect loads its info and capabilities."""
    import oterm.app.chat_edit as ce

    class _Show(dict):
        parameters = "temperature 0.7\ntop_p 0.95"

        def get(self, key, default=""):
            if key == "capabilities":
                return ["tools", "thinking", "vision", "completion"]
            if key == "system":
                return "default system"
            return default

    monkeypatch.setattr(ce.ollama, "show_model", lambda m: _Show())

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        await screen._load_model_info("some-model")
        await pilot.pause()

        assert screen.query_one("#temperature-input", Input).value == "0.7"
        assert screen.query_one("#top-p-input", Input).value == "0.95"
        # Save button becomes enabled
        assert screen.query_one("#save-btn", Button).disabled is False


async def test_load_model_info_show_failure_notifies(app_config, monkeypatch):
    import oterm.app.chat_edit as ce

    def boom(m):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(ce.ollama, "show_model", boom)

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        await screen._load_model_info("m")
        await pilot.pause()

        assert any(
            "Failed to load model" in n.message for n in list(app._notifications)
        )


async def test_provider_change_resets_model(app_config, monkeypatch):
    """Switching provider clears model + reloads the model list for the new provider."""
    import oterm.providers as prov

    monkeypatch.setattr(prov, "list_models", lambda p: ["gpt-4o", "gpt-5"])
    monkeypatch.setattr(prov, "get_available_providers", lambda: ["ollama", "openai"])

    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model)
        app.push_screen(screen)
        await pilot.pause()

        from textual.widgets import Select

        event = Select.Changed(screen.query_one("#provider-select", Select), "openai")
        await screen.on_select_changed(event)
        await pilot.pause()

        assert screen.provider == "openai"
        assert screen.model_name == ""


async def test_load_models_failure_notifies(app_config, monkeypatch):
    import oterm.app.chat_edit as ce

    def boom():
        raise RuntimeError("list failed")

    monkeypatch.setattr(ce.ollama, "list_models", boom)

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        await screen._load_models_for_provider("ollama")
        await pilot.pause()

        assert any(
            "Failed to load models" in n.message for n in list(app._notifications)
        )
