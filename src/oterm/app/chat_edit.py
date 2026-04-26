import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ollama import ListResponse, ShowResponse
from textual import on
from textual.app import ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
)
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, TextArea

from oterm.app.widgets.caps import Capabilities
from oterm.app.widgets.model_select import ModelSelect
from oterm.app.widgets.tool_select import ToolSelector
from oterm.providers import (
    get_available_providers,
    get_provider_name,
    list_models,
    ollama,
)
from oterm.providers.capabilities import get_capabilities
from oterm.providers.settings import get_supported_setting_keys
from oterm.types import ChatModel


@dataclass(frozen=True)
class _ParamSpec:
    key: str
    label: str
    parser: Callable[[str], Any]
    placeholder: str
    range_check: Callable[[Any], bool] | None = None
    range_text: str | None = None

    @property
    def input_id(self) -> str:
        return f"{self.key.replace('_', '-')}-input"


_PARAM_SPECS: tuple[_ParamSpec, ...] = (
    _ParamSpec(
        key="temperature",
        label="Temperature",
        parser=float,
        placeholder="0.0 - 2.0",
        range_check=lambda v: 0.0 <= v <= 2.0,
        range_text="between 0.0 and 2.0",
    ),
    _ParamSpec(
        key="top_p",
        label="Top P",
        parser=float,
        placeholder="0.0 - 1.0",
        range_check=lambda v: 0.0 <= v <= 1.0,
        range_text="between 0.0 and 1.0",
    ),
    _ParamSpec(
        key="max_tokens",
        label="Max Tokens",
        parser=int,
        placeholder="e.g. 4096",
        range_check=lambda v: v > 0,
        range_text="greater than 0",
    ),
    _ParamSpec(
        key="seed",
        label="Seed",
        parser=int,
        placeholder="integer",
    ),
)


class ChatEdit(ModalScreen[str]):
    models: list[str] = []
    models_info: dict[str, ShowResponse] = {}
    models_size: dict[str, int] = {}

    provider: reactive[str] = reactive("ollama")
    model_name: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: ShowResponse
    system: reactive[str] = reactive("")
    parameters: reactive[dict[str, Any]] = reactive({})
    tools: reactive[list[str]] = reactive([])
    edit_mode: reactive[bool] = reactive(False)
    thinking: reactive[bool] = reactive(False)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "save", "Save"),
    ]

    def __init__(
        self,
        chat_model: ChatModel | None = None,
        edit_mode: bool = False,
    ) -> None:
        super().__init__()

        if chat_model is None:
            chat_model = ChatModel()

        self.chat_model = chat_model
        self.provider = chat_model.provider
        self.model_name = chat_model.model or ""
        self.system = chat_model.system or ""
        self.parameters = chat_model.parameters
        self.tools = chat_model.tools
        self.edit_mode = edit_mode
        self.thinking = chat_model.thinking
        self._loaded_model: str = ""

    def _return_chat_meta(self) -> None:
        model = self.query_one(ModelSelect).value.strip()
        if not model:
            self.app.notify("Please enter a model name", severity="error")
            return

        system = self.query_one(".system", TextArea).text
        model_system = getattr(self, "model_info", {}).get("system", "")
        system = system if system != model_system else None

        parameters: dict[str, Any] = {}
        for spec in _PARAM_SPECS:
            if spec.key not in get_supported_setting_keys(self.provider):
                continue
            raw = self.query_one(f"#{spec.input_id}", Input).value.strip()
            if not raw:
                continue
            try:
                value = spec.parser(raw)
            except ValueError:
                self.app.notify(f"Invalid {spec.label} value", severity="error")
                return
            if spec.range_check is not None and not spec.range_check(value):
                self.app.notify(
                    f"{spec.label} must be {spec.range_text}", severity="error"
                )
                return
            parameters[spec.key] = value

        self.tools = self.query_one(ToolSelector).selected
        self.thinking = self.query_one("#thinking-checkbox", Checkbox).value

        updated_chat_model = ChatModel(
            id=self.chat_model.id,
            name=self.chat_model.name,
            model=model,
            system=system,
            provider=self.provider,
            parameters=parameters,
            tools=self.tools,
            thinking=self.thinking,
        )

        self.dismiss(updated_chat_model.model_dump_json(exclude_none=True))

    def action_cancel(self) -> None:
        self.dismiss()

    def action_save(self) -> None:
        self._return_chat_meta()

    async def on_mount(self) -> None:
        provider_select = self.query_one("#provider-select", Select)
        provider_select.value = self.provider

        if self.provider not in get_available_providers():
            self.app.notify(
                f"Provider {get_provider_name(self.provider)!r} is not currently "
                "available. Check your environment or `openaiCompatible` config.",
                severity="warning",
            )

        await self._load_models_for_provider(self.provider)

        model_select = self.query_one(ModelSelect)
        if self.chat_model.model:
            model_select.set_value(self.chat_model.model)
            await self._load_model_info(self.chat_model.model)

        provider_select.disabled = self.edit_mode
        model_select.disabled = self.edit_mode

    async def _load_models_for_provider(self, provider: str) -> None:
        """Fetch models and update the model select."""
        try:
            if provider == "ollama":
                list_response: ListResponse = await asyncio.to_thread(
                    ollama.list_models
                )
                self.models = [m.model or "" for m in list_response.models]
                self.models_size = {}
                for m in list_response.models:
                    if m.model:  # pragma: no branch
                        self.models_size[m.model] = m["size"]
            else:
                self.models = await asyncio.to_thread(list_models, provider)
        except Exception as e:
            self.app.notify(
                f"Failed to load models for {provider}: {e}", severity="error"
            )
            self.models = []
        self.query_one(ModelSelect).set_options(self.models)

    async def _load_model_info(self, model: str) -> None:
        """Load model info (capabilities, system prompt, parameters) for the given model."""
        if not model or model == self._loaded_model:
            return
        self._loaded_model = model

        self.model_name = model
        self.query_one(".name", Label).update(model)

        if self.provider == "ollama":
            size = self.models_size.get(model)
            if size:
                self.bytes = size
                self.query_one(".size", Label).update(f"{(self.bytes / 1.0e9):.2f} GB")
            else:
                self.query_one(".size", Label).update("")

            meta = self.models_info.get(model)
            if not meta:
                try:
                    meta = await asyncio.to_thread(ollama.show_model, model)
                except Exception as e:
                    self.app.notify(f"Failed to load model info: {e}", severity="error")
                    return
                self.models_info[model] = meta

            self.model_info = meta
            self._populate_parameter_inputs(self.parameters)
            self.query_one(".system", TextArea).load_text(
                self.system or self.model_info.get("system", "")
            )
            capabilities: list[str] = list(self.model_info.get("capabilities", []))
        else:
            self.query_one(".size", Label).update("")
            caps = get_capabilities(self.provider, model)
            capabilities = []
            if caps.supports_tools:
                capabilities.append("tools")
            if caps.supports_thinking:
                capabilities.append("thinking")
            if caps.supports_vision:
                capabilities.append("vision")

        self._update_capabilities_ui(capabilities)
        self.query_one("#save-btn", Button).disabled = False

    def _update_capabilities_ui(self, capabilities: list[str]) -> None:
        tool_selector = self.query_one(ToolSelector)
        tool_selector.disabled = "tools" not in capabilities

        thinking_checkbox = self.query_one("#thinking-checkbox", Checkbox)
        thinking_checkbox.disabled = "thinking" not in capabilities

        display_caps = [c for c in capabilities if c not in ("completion", "embedding")]
        self.query_one(".caps", Capabilities).caps = display_caps  # ty: ignore[invalid-assignment]

    def _populate_parameter_inputs(self, parameters: dict[str, Any]) -> None:
        supported = get_supported_setting_keys(self.provider)
        for spec in _PARAM_SPECS:
            if spec.key not in supported:
                continue
            self.query_one(f"#{spec.input_id}", Input).value = str(
                parameters.get(spec.key, "")
            )

    @on(ModelSelect.Submitted)
    async def on_model_submitted(self, event: ModelSelect.Submitted) -> None:
        await self._load_model_info(event.value)

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            new_provider = str(event.value)
            if new_provider != self.provider:
                self.provider = new_provider
                self.model_name = ""
                self._loaded_model = ""
                self.query_one(".name", Label).update("")
                self.query_one(".size", Label).update("")
                self.query_one(".caps", Capabilities).caps = []
                self.query_one(ModelSelect).set_value("")
                self.query_one("#save-btn", Button).disabled = True
                await self._load_models_for_provider(new_provider)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "save":
            self._return_chat_meta()
        else:
            self.dismiss()

    def compose(self) -> ComposeResult:
        providers = get_available_providers()
        provider_options = [(get_provider_name(p), p) for p in providers]
        # Preserve a chat's saved provider even when the endpoint is no longer
        # configured (e.g. an `openai-compat/<name>` removed from config.json).
        # Without this the Select would reject the value at mount time.
        if self.provider and self.provider not in providers:
            provider_options.insert(
                0, (f"{get_provider_name(self.provider)} (unavailable)", self.provider)
            )

        with Container(id="chat-edit-screen", classes="screen-container full-height"):
            with Horizontal(id="top-labels"):
                with Horizontal(classes="info-left"):
                    yield Label("Model:", classes="title")
                    yield Label("", classes="name")
                    yield Label("Size:", classes="title")
                    yield Label("", classes="size")
                    yield Label("Caps:", classes="title")
                    yield Capabilities([], classes="caps")
                yield Label("System:", classes="title info-right")
            with Horizontal(id="top-row"):
                with Vertical():
                    yield Select(
                        provider_options,
                        id="provider-select",
                        value=self.provider,
                        allow_blank=False,
                    )
                    yield ModelSelect(id="model-select")
                with Vertical():
                    yield TextArea(self.system, classes="system log")
            with Horizontal(id="bottom-labels"):
                yield Label("Tools:", classes="title")
                yield Label("Parameters:", classes="title")
            with Horizontal(id="bottom-row"):
                with Vertical():
                    yield ToolSelector(
                        id="tool-selector-container", selected=self.tools
                    )
                with Vertical():
                    visible_specs = [
                        s
                        for s in _PARAM_SPECS
                        if s.key in get_supported_setting_keys(self.provider)
                    ]
                    for i in range(0, len(visible_specs), 2):
                        with Horizontal(classes="param-row"):
                            for spec in visible_specs[i : i + 2]:
                                yield Label(f"{spec.label}:", classes="title")
                                yield Input(
                                    value=str(self.parameters.get(spec.key, "")),
                                    id=spec.input_id,
                                    placeholder=spec.placeholder,
                                )
                    with Horizontal(classes="param-row"):
                        yield Label("Thinking:", classes="title")
                        yield Checkbox(
                            "",
                            id="thinking-checkbox",
                            name="thinking",
                            value=self.thinking,
                        )

            with Horizontal(classes="button-container"):
                yield Button(
                    "Save",
                    id="save-btn",
                    name="save",
                    disabled=True,
                    variant="primary",
                )
                yield Button("Cancel", name="cancel")
