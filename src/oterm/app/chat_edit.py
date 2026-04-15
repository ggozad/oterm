import asyncio
from typing import Any

from ollama import ListResponse, ShowResponse
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
)
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, Select, TextArea

from oterm.app.widgets.caps import Capabilities
from oterm.app.widgets.tool_select import ToolSelector
from oterm.ollamaclient import parse_ollama_parameters
from oterm.providers import (
    get_available_providers,
    get_provider_name,
    list_models,
    ollama,
)
from oterm.providers.capabilities import get_capabilities
from oterm.types import ChatModel


class ChatEdit(ModalScreen[str]):
    models: list[str] = []
    models_info: dict[str, ShowResponse] = {}
    models_size: dict[str, int] = {}

    provider: reactive[str] = reactive("ollama")
    model_name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: ShowResponse
    system: reactive[str] = reactive("")
    parameters: reactive[dict[str, Any]] = reactive({})
    last_highlighted_index: dict[str, int | None] = {}
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
        if ":" in (chat_model.model or ""):
            self.model_name, self.tag = chat_model.model.split(":", 1)
        else:
            self.model_name = chat_model.model or ""
            self.tag = ""
        self.system = chat_model.system or ""
        self.parameters = chat_model.parameters
        self.tools = chat_model.tools
        self.edit_mode = edit_mode
        self.thinking = chat_model.thinking

    def _return_chat_meta(self) -> None:
        if self.provider == "ollama":
            model = f"{self.model_name}:{self.tag}" if self.tag else self.model_name
        else:
            model = self.model_name

        system = self.query_one(".system", TextArea).text
        model_system = getattr(self, "model_info", {}).get("system", "")
        system = system if system != model_system else None

        parameters: dict[str, Any] = {}
        temp_input = self.query_one("#temperature-input", Input)
        top_p_input = self.query_one("#top-p-input", Input)
        max_tokens_input = self.query_one("#max-tokens-input", Input)

        if temp_input.value.strip():
            try:
                temp = float(temp_input.value)
                if not 0.0 <= temp <= 2.0:
                    self.app.notify(
                        "Temperature must be between 0.0 and 2.0", severity="error"
                    )
                    return
                parameters["temperature"] = temp
            except ValueError:
                self.app.notify("Invalid temperature value", severity="error")
                return

        if top_p_input.value.strip():
            try:
                top_p = float(top_p_input.value)
                if not 0.0 <= top_p <= 1.0:
                    self.app.notify(
                        "Top P must be between 0.0 and 1.0", severity="error"
                    )
                    return
                parameters["top_p"] = top_p
            except ValueError:
                self.app.notify("Invalid Top P value", severity="error")
                return

        if max_tokens_input.value.strip():
            try:
                max_tokens = int(max_tokens_input.value)
                if max_tokens <= 0:
                    self.app.notify(
                        "Max Tokens must be greater than 0", severity="error"
                    )
                    return
                parameters["max_tokens"] = max_tokens
            except ValueError:
                self.app.notify("Invalid Max Tokens value", severity="error")
                return

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

    def select_model(self, model: str) -> None:
        select = self.query_one("#model-select", OptionList)
        for index, option in enumerate(select._options):
            if str(option.prompt) == model:
                select.highlighted = index
                return
        if select._options:
            select.highlighted = 0

    async def on_mount(self) -> None:
        provider_select = self.query_one("#provider-select", Select)
        provider_select.value = self.provider

        await self._load_models_for_provider(self.provider)

        if self.model_name:
            if self.provider == "ollama" and self.tag:
                self.select_model(f"{self.model_name}:{self.tag}")
            else:
                self.select_model(self.model_name)

        provider_select.disabled = self.edit_mode
        model_select = self.query_one("#model-select", OptionList)
        model_select.disabled = self.edit_mode

    async def _load_models_for_provider(self, provider: str) -> None:
        option_list = self.query_one("#model-select", OptionList)
        option_list.clear_options()
        self.models_info = {}
        self.models_size = {}

        if provider == "ollama":
            list_response: ListResponse = await asyncio.to_thread(ollama.list_models)
            self.models = [m.model or "" for m in list_response.models]
            for m in list_response.models:
                if m.model:
                    self.models_size[m.model] = m["size"]
            for model in self.models:
                option_list.add_option(option=self.model_option(model))
        else:
            self.models = list_models(provider)
            for model in self.models:
                option_list.add_option(option=self.model_option(model))

        last_index = ChatEdit.last_highlighted_index.get(provider)
        if last_index is not None and last_index < len(self.models):
            option_list.highlighted = last_index
        elif self.models:
            option_list.highlighted = 0

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "provider-select":
            new_provider = str(event.value)
            if new_provider != self.provider:
                self.provider = new_provider
                self.model_name = ""
                self.tag = ""
                self.query_one(".name", Label).update("")
                self.query_one(".tag", Label).update("")
                self.query_one(".size", Label).update("")
                self.query_one(".caps", Capabilities).caps = []
                await self._load_models_for_provider(new_provider)

    def _populate_parameter_inputs(self, parameters: dict[str, Any]) -> None:
        self.query_one("#temperature-input", Input).value = str(
            parameters.get("temperature", "")
        )
        self.query_one("#top-p-input", Input).value = str(parameters.get("top_p", ""))
        max_tokens = parameters.get("max_tokens", parameters.get("num_predict", ""))
        self.query_one("#max-tokens-input", Input).value = str(max_tokens)

    async def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = str(option.option.prompt)

        if self.provider == "ollama":
            if ":" in model:
                name, tag = model.split(":", 1)
            else:
                name, tag = model, ""
            self.model_name = name
            self.tag = tag

            self.query_one(".name", Label).update(name)
            self.query_one(".tag", Label).update(tag)

            size = self.models_size.get(model)
            if size:
                self.bytes = size
                self.query_one(".size", Label).update(f"{(self.bytes / 1.0e9):.2f} GB")

            meta = self.models_info.get(model)
            if not meta:
                meta = await asyncio.to_thread(ollama.show_model, model)
                self.models_info[model] = meta

            self.model_info = meta
            if not self.edit_mode:
                self.parameters = parse_ollama_parameters(
                    self.model_info.parameters or ""
                )
            self._populate_parameter_inputs(self.parameters)
            self.query_one(".system", TextArea).load_text(
                self.system or self.model_info.get("system", "")
            )

            capabilities: list[str] = list(self.model_info.get("capabilities", []))
        else:
            self.model_name = model
            self.tag = ""

            self.query_one(".name", Label).update(model)
            self.query_one(".tag", Label).update("")
            self.query_one(".size", Label).update("N/A")

            caps = get_capabilities(self.provider, model)
            capabilities = []
            if caps.supports_tools:
                capabilities.append("tools")
            if caps.supports_thinking:
                capabilities.append("thinking")
            if caps.supports_vision:
                capabilities.append("vision")

        tools_supported = "tools" in capabilities
        tool_selector = self.query_one(ToolSelector)
        tool_selector.disabled = not tools_supported

        thinking_checkbox = self.query_one("#thinking-checkbox", Checkbox)
        thinking_checkbox.disabled = "thinking" not in capabilities

        display_caps = [c for c in capabilities if c not in ("completion", "embedding")]
        self.query_one(".caps", Capabilities).caps = display_caps  # type: ignore

        self.query_one("#save-btn", Button).disabled = False
        ChatEdit.last_highlighted_index[self.provider] = option.option_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "save":
            self._return_chat_meta()
        else:
            self.dismiss()

    @staticmethod
    def model_option(model: str) -> Text:
        return Text(model)

    def compose(self) -> ComposeResult:
        providers = get_available_providers()
        provider_options = [(get_provider_name(p), p) for p in providers]

        with Container(id="chat-edit-screen", classes="screen-container full-height"):
            with Horizontal(id="model-info"):
                yield Label("Model:", classes="title")
                yield Label(f"{self.model_name}", classes="name")
                yield Label("Tag:", classes="title")
                yield Label(f"{self.tag}", classes="tag")
                yield Label("Size:", classes="title")
                yield Label("", classes="size")
                yield Label("Caps:", classes="title")
                yield Capabilities([], classes="caps")
            with Horizontal(id="top-row"):
                with Vertical():
                    yield Select(
                        provider_options,
                        id="provider-select",
                        value=self.provider,
                        allow_blank=False,
                    )
                    yield OptionList(id="model-select")
                with Vertical():
                    yield Label("System:", classes="title")
                    yield TextArea(self.system, classes="system log")
            with Horizontal(id="bottom-row"):
                with Vertical():
                    yield Label("Tools:", classes="title")
                    yield ToolSelector(
                        id="tool-selector-container", selected=self.tools
                    )
                with Vertical():
                    with Horizontal(classes="param-row"):
                        yield Label("Temperature:", classes="title")
                        yield Input(
                            value=str(self.parameters.get("temperature", "")),
                            id="temperature-input",
                            placeholder="0.0 - 2.0",
                        )
                        yield Label("Top P:", classes="title")
                        yield Input(
                            value=str(self.parameters.get("top_p", "")),
                            id="top-p-input",
                            placeholder="0.0 - 1.0",
                        )
                    with Horizontal(classes="param-row"):
                        yield Label("Max Tokens:", classes="title")
                        yield Input(
                            value=str(
                                self.parameters.get(
                                    "max_tokens",
                                    self.parameters.get("num_predict", ""),
                                )
                            ),
                            id="max-tokens-input",
                            placeholder="e.g. 4096",
                        )
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
