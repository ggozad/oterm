from ollama import Options, ShowResponse
from pydantic import ValidationError
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
)
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, RadioSet, TextArea

from oterm.app.widgets.caps import Capabilities
from oterm.app.widgets.tool_select import ToolSelector
from oterm.config import envConfig
from oterm.minimaxclient import MiniMaxLLM
from oterm.ollamaclient import (
    OllamaLLM,
    jsonify_options,
    parse_format,
    parse_ollama_parameters,
)
from oterm.types import ChatModel, OtermOllamaOptions, Tool


class ChatEdit(ModalScreen[str]):
    models = []
    models_info: dict[str, ShowResponse | Any] = {}

    model_name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: ShowResponse | Any = None
    system: reactive[str] = reactive("")
    parameters: reactive[Options] = reactive(Options())
    format: reactive[str] = reactive("")
    keep_alive: reactive[int] = reactive(5)
    last_highlighted_index = None
    tools: reactive[list[Tool]] = reactive([])
    edit_mode: reactive[bool] = reactive(False)
    thinking: reactive[bool] = reactive(False)
    provider: reactive[str] = reactive("ollama")

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
        parts = chat_model.model.split(":", 1) if chat_model.model else ["", ""]
        self.model_name = parts[0]
        self.tag = parts[1] if len(parts) > 1 else ""
        self.system = chat_model.system or ""
        self.parameters = chat_model.parameters
        self.format = chat_model.format
        self.keep_alive = chat_model.keep_alive
        self.tools = chat_model.tools
        self.edit_mode = edit_mode
        self.thinking = chat_model.thinking
        self.provider = chat_model.provider

    def _return_chat_meta(self) -> None:
        if self.tag:
            model = f"{self.model_name}:{self.tag}"
        else:
            model = self.model_name
        system = self.query_one(".system", TextArea).text
        system = system if system != (self.model_info.get("system", "") if self.model_info else "") else None
        keep_alive = int(self.query_one(".keep-alive", Input).value)
        p_area = self.query_one(".parameters", TextArea)
        try:
            parameters = OtermOllamaOptions.model_validate_json(
                p_area.text, strict=True
            )

            if isinstance(parameters.stop, str):
                parameters.stop = [parameters.stop]

        except ValidationError:
            self.app.notify("Error validating parameters", severity="error")
            p_area = self.query_one(".parameters", TextArea)
            p_area.styles.animate("opacity", 0.0, final_value=1.0, duration=0.5)
            return

        f_area = self.query_one(".format", TextArea)
        try:
            parse_format(f_area.text)
            format = f_area.text
        except Exception:
            self.app.notify("Error parsing format", severity="error")
            f_area.styles.animate("opacity", 0.0, final_value=1.0, duration=0.5)
            return

        self.tools = self.query_one(ToolSelector).selected
        self.thinking = self.query_one("#thinking-checkbox", Checkbox).value

        # Create updated chat model
        updated_chat_model = ChatModel(
            id=self.chat_model.id,
            name=self.chat_model.name,
            model=model,
            provider=self.provider,
            system=system,
            format=format,
            parameters=parameters,
            keep_alive=keep_alive,
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
                break

    async def on_mount(self) -> None:
        # Set initial provider in the RadioSet
        radio_set = self.query_one("#provider-select", RadioSet)
        if self.provider == "minimax":
            radio_set.pressed_index = 1
        else:
            radio_set.pressed_index = 0

        self._load_models()

        # Disable the model select widget if we are in edit mode.
        widget = self.query_one("#model-select", OptionList)
        widget.disabled = self.edit_mode

    def _load_models(self) -> None:
        """Load models for the currently selected provider."""
        if self.provider == "minimax":
            response = MiniMaxLLM.list()
            self.models = response.models
            models = [model.model or "" for model in self.models]
            for model in models:
                info = MiniMaxLLM.show(model)
                self.models_info[model] = info
        else:
            self.models = OllamaLLM.list().models
            models = [model.model or "" for model in self.models]
            for model in models:
                info = OllamaLLM.show(model)
                self.models_info[model] = info

        option_list = self.query_one("#model-select", OptionList)
        option_list.clear_options()
        for model in models:
            option_list.add_option(option=self.model_option(model))
        option_list.highlighted = self.last_highlighted_index

        if self.model_name:
            model_str = f"{self.model_name}:{self.tag}" if self.tag else self.model_name
            self.select_model(model_str)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle provider selection change."""
        provider = "minimax" if event.index == 1 else "ollama"
        if provider != self.provider:
            self.provider = provider
            self.model_name = ""
            self.tag = ""
            self.models_info = {}
            ChatEdit.last_highlighted_index = None
            self._load_models()

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_meta = next((m for m in self.models if m.model == str(model)), None)
        if model_meta:
            parts = (model_meta.model or "").split(":", 1)
            name = parts[0]
            tag = parts[1] if len(parts) > 1 else ""
            self.model_name = name
            widget = self.query_one(".name", Label)
            widget.update(f"{self.model_name}")

            self.tag = tag
            widget = self.query_one(".tag", Label)
            widget.update(f"{self.tag}")

            size = model_meta["size"] if "size" in model_meta.__dict__ or hasattr(model_meta, "size") else 0
            self.bytes = size
            widget = self.query_one(".size", Label)
            if size > 0:
                widget.update(f"{(self.bytes / 1.0e9):.2f} GB")
            else:
                widget.update("cloud" if self.provider == "minimax" else "N/A")

            meta = self.models_info.get(model_meta.model or "")
            self.model_info = meta  # type: ignore
            if not self.edit_mode:
                params_text = self.model_info.parameters or "" if self.model_info else ""
                if self.provider == "ollama":
                    self.parameters = parse_ollama_parameters(params_text)
                else:
                    self.parameters = Options()
            widget = self.query_one(".parameters", TextArea)
            widget.load_text(jsonify_options(self.parameters))
            widget = self.query_one(".system", TextArea)

            widget.load_text(self.system or (self.model_info.get("system", "") if self.model_info else ""))

            capabilities: list[str] = self.model_info.get("capabilities", []) if self.model_info else []
            tools_supported = "tools" in capabilities
            tool_selector = self.query_one(ToolSelector)
            tool_selector.disabled = not tools_supported

            thinking_checkbox = self.query_one("#thinking-checkbox", Checkbox)
            thinking_checkbox.disabled = "thinking" not in capabilities

            if "completion" in capabilities:
                capabilities.remove("completion")
            if "embedding" in capabilities:
                capabilities.remove("embedding")

            widget = self.query_one(".caps", Capabilities)
            widget.caps = capabilities  # type: ignore

        # Now that there is a model selected we can save the chat.
        save_button = self.query_one("#save-btn", Button)
        save_button.disabled = False
        ChatEdit.last_highlighted_index = option.option_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "save":
            self._return_chat_meta()
        else:
            self.dismiss()

    @staticmethod
    def model_option(model: str) -> Text:
        return Text(model)

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container full-height"):
            with Horizontal():
                with Vertical():
                    with Horizontal(id="provider-info"):
                        yield Label("Provider:", classes="title")
                        with RadioSet(id="provider-select"):
                            from textual.widgets import RadioButton

                            yield RadioButton("Ollama", value=self.provider == "ollama")
                            minimax_available = bool(envConfig.MINIMAX_API_KEY)
                            yield RadioButton(
                                "MiniMax",
                                value=self.provider == "minimax",
                                disabled=not minimax_available,
                            )
                    with Horizontal(id="model-info"):
                        yield Label("Model:", classes="title")
                        yield Label(f"{self.model_name}", classes="name")
                        yield Label("Tag:", classes="title")
                        yield Label(f"{self.tag}", classes="tag")
                        yield Label("Size:", classes="title")
                        yield Label(f"{self.size}", classes="size")
                        yield Label("Caps:", classes="title")
                        yield Capabilities([], classes="caps")
                    yield OptionList(id="model-select")
                    yield Label("Tools:", classes="title")
                    yield ToolSelector(
                        id="tool-selector-container", selected=self.tools
                    )

                with Vertical():
                    yield Label("System:", classes="title")
                    yield TextArea(self.system, classes="system log")
                    yield Label("Parameters:", classes="title")
                    yield TextArea(
                        jsonify_options(self.parameters),
                        classes="parameters log",
                        language="json",
                    )
                    yield Label("Format:", classes="title")
                    yield TextArea(
                        self.format or "",
                        classes="format log",
                        language="json",
                    )

                    with Horizontal():
                        with Horizontal():
                            yield Checkbox(
                                "Thinking",
                                id="thinking-checkbox",
                                name="thinking",
                                value=self.thinking,
                            )
                            yield Label(
                                "Keep-alive (min)", classes="title keep-alive-label"
                            )
                            yield Input(
                                classes="keep-alive", value=str(self.keep_alive)
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
