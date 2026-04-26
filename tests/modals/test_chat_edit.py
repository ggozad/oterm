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
        assert screen.query_one("#seed-input", Input)
        assert screen.query_one("#thinking-checkbox", Checkbox)
        assert screen.query_one("#save-btn", Button)


async def test_compose_renders_param_inputs_for_anthropic(app_config, monkeypatch):
    """Common sampling fields are surfaced for every supported provider."""
    import oterm.providers as prov

    monkeypatch.setattr(prov, "list_models", lambda p: ["claude-sonnet-4"])
    monkeypatch.setattr(
        prov, "get_available_providers", lambda: ["ollama", "anthropic"]
    )

    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(model="claude-sonnet-4", provider="anthropic")
        app.push_screen(ChatEdit(chat_model=chat_model))
        await pilot.pause()
        screen = app.screen
        for input_id in (
            "#temperature-input",
            "#top-p-input",
            "#max-tokens-input",
            "#seed-input",
        ):
            assert screen.query_one(input_id, Input)


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
        ("#temperature-input", "nope", "Invalid Temperature"),
        ("#temperature-input", "3.0", "Temperature must be"),
        ("#top-p-input", "nope", "Invalid Top P"),
        ("#top-p-input", "2.0", "Top P must be"),
        ("#max-tokens-input", "nope", "Invalid Max Tokens"),
        ("#max-tokens-input", "-1", "Max Tokens must be"),
        ("#seed-input", "nope", "Invalid Seed"),
        ("#seed-input", "1.5", "Invalid Seed"),
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
        screen.query_one("#seed-input", Input).value = "1234"
        await pilot.pause()

        screen._return_chat_meta()
        await pilot.pause()

        assert received and received[0]
        payload = json.loads(received[0])
        assert payload["parameters"] == {
            "temperature": 0.3,
            "top_p": 0.9,
            "max_tokens": 512,
            "seed": 1234,
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
    """Selecting a model via ModelSelect loads its capabilities and system prompt."""
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

        assert screen.query_one(".system", TextArea).text == "default system"
        assert screen.query_one("#temperature-input", Input).value == ""
        assert screen.query_one("#top-p-input", Input).value == ""
        assert screen.query_one("#save-btn", Button).disabled is False


async def test_chat_with_legacy_ollama_keys_loads(app_config):
    """A chat persisted with Ollama-native keys (num_ctx) must still open."""
    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(
            id=1,
            model="llama3",
            provider="ollama",
            parameters={"num_ctx": 8192, "temperature": 0.4},
        )
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one("#temperature-input", Input).value == "0.4"
        assert screen.parameters["num_ctx"] == 8192


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


async def test_edit_chat_with_unconfigured_openai_compat(app_config, monkeypatch):
    """Opening an existing chat whose openai-compat endpoint is no longer
    configured must not crash. The provider stays on its saved value (the
    Select is disabled in edit mode anyway) so saving preserves the original.
    """
    import oterm.providers as prov

    # Endpoint is no longer in the available list.
    monkeypatch.setattr(prov, "get_available_providers", lambda: ["ollama"])

    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(
            id=1, name="x", model="some-model", provider="openai-compat/gone"
        )
        screen = ChatEdit(chat_model=chat_model, edit_mode=True)
        app.push_screen(screen)
        await pilot.pause()

        # No InvalidSelectValueError; provider preserved.
        assert screen.provider == "openai-compat/gone"
        assert any(
            "not currently available" in n.message for n in list(app._notifications)
        )


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


async def test_load_model_info_skips_when_already_loaded(app_config, monkeypatch):
    """A second call with the same model name short-circuits without re-fetching."""
    import oterm.app.chat_edit as ce

    calls: list[str] = []

    def show(m):
        calls.append(m)

        class _Show(dict):
            parameters = ""

            def get(self, key, default=""):
                return default

        return _Show()

    monkeypatch.setattr(ce.ollama, "show_model", show)

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        await screen._load_model_info("dup-model")
        await screen._load_model_info("dup-model")
        await pilot.pause()
        assert calls == ["dup-model"]


async def test_load_model_info_uses_cached_meta(app_config, monkeypatch):
    """Cached models_info entries skip the ollama.show_model fetch."""
    import oterm.app.chat_edit as ce

    calls: list[str] = []

    def show(m):
        calls.append(m)
        raise AssertionError("show_model should not be called when cached")

    monkeypatch.setattr(ce.ollama, "show_model", show)

    class _Cached(dict):
        parameters = ""

        def __bool__(self) -> bool:
            return True

        def get(self, key, default=""):
            if key == "capabilities":
                return ["tools"]
            return default

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        ChatEdit.models_info["cached-model"] = _Cached()  # ty: ignore[invalid-assignment]
        try:
            await screen._load_model_info("cached-model")
            await pilot.pause()
            assert calls == []
        finally:
            ChatEdit.models_info.pop("cached-model", None)


async def test_load_model_info_non_ollama_populates_caps(app_config, monkeypatch):
    """For non-ollama providers, caps come from get_capabilities."""
    import oterm.app.chat_edit as ce
    from oterm.providers.capabilities import ModelCapabilities

    monkeypatch.setattr(
        ce,
        "get_capabilities",
        lambda provider, model: ModelCapabilities(
            supports_tools=True, supports_thinking=True, supports_vision=True
        ),
    )

    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(model="claude-sonnet", provider="anthropic")
        screen = ChatEdit(chat_model=chat_model)
        screen.provider = "anthropic"
        app.push_screen(screen)
        await pilot.pause()

        await screen._load_model_info("claude-sonnet")
        await pilot.pause()

        from oterm.app.widgets.caps import Capabilities

        caps_widget = screen.query_one(".caps", Capabilities)
        assert set(caps_widget.caps) == {"tools", "thinking", "vision"}


async def test_load_model_info_non_ollama_no_caps(app_config, monkeypatch):
    """A non-ollama provider with no capabilities renders an empty caps strip."""
    import oterm.app.chat_edit as ce
    from oterm.providers.capabilities import ModelCapabilities

    monkeypatch.setattr(
        ce,
        "get_capabilities",
        lambda provider, model: ModelCapabilities(),
    )

    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(model="basic", provider="anthropic")
        screen = ChatEdit(chat_model=chat_model)
        screen.provider = "anthropic"
        app.push_screen(screen)
        await pilot.pause()

        await screen._load_model_info("basic")
        await pilot.pause()

        from oterm.app.widgets.caps import Capabilities

        caps_widget = screen.query_one(".caps", Capabilities)
        assert list(caps_widget.caps) == []


async def test_on_model_submitted_loads_model(app_config, monkeypatch):
    import oterm.app.chat_edit as ce

    loaded: list[str] = []

    async def fake_load(self, model):
        loaded.append(model)

    monkeypatch.setattr(ce.ChatEdit, "_load_model_info", fake_load)

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        await screen.on_model_submitted(ModelSelect.Submitted("picked"))
        await pilot.pause()
        assert loaded == ["picked"]


async def test_on_select_changed_ignores_other_selects(app_config):
    """Select.Changed for non-provider selects is a no-op."""
    from textual.widgets import Select

    app = _Host()
    async with app.run_test() as pilot:
        screen = ChatEdit()
        app.push_screen(screen)
        await pilot.pause()

        # Construct a fresh Select with no id; the handler must short-circuit
        # because event.select.id != "provider-select".
        fake_select: Select = Select([("a", "a")], id="other-select")
        ev = Select.Changed(fake_select, "ollama")
        original_provider = screen.provider
        await screen.on_select_changed(ev)
        await pilot.pause()
        assert screen.provider == original_provider


async def test_on_select_changed_same_provider_is_noop(app_config):
    """Selecting the already-active provider does not reset state."""
    from textual.widgets import Select

    app = _Host()
    async with app.run_test() as pilot:
        chat_model = ChatModel(model="llama3", provider="ollama")
        screen = ChatEdit(chat_model=chat_model)
        app.push_screen(screen)
        await pilot.pause()
        screen.model_name = "llama3"

        provider_select = screen.query_one("#provider-select", Select)
        ev = Select.Changed(provider_select, "ollama")
        await screen.on_select_changed(ev)
        await pilot.pause()
        # No reset — model_name preserved.
        assert screen.model_name == "llama3"
