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
from textual.widgets import Button, Checkbox, Input, Label, OptionList, TextArea

from oterm.app.widgets.tool_select import ToolSelector
from oterm.ollamaclient import (
    OllamaLLM,
    jsonify_options,
    parse_format,
    parse_ollama_parameters,
)
from oterm.types import ChatModel, OtermOllamaOptions, Tool


class ChatEdit(ModalScreen[str]):
    models = []
    models_info: dict[str, ShowResponse] = {}

    model_name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: ShowResponse
    system: reactive[str] = reactive("")
    parameters: reactive[Options] = reactive(Options())
    format: reactive[str] = reactive("")
    keep_alive: reactive[int] = reactive(5)
    last_highlighted_index = None
    tools: reactive[list[Tool]] = reactive([])
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
        self.model_name, self.tag = (
            chat_model.model.split(":") if chat_model.model else ("", "")
        )
        self.system = chat_model.system or ""
        self.parameters = chat_model.parameters
        self.format = chat_model.format
        self.keep_alive = chat_model.keep_alive
        self.tools = chat_model.tools
        self.edit_mode = edit_mode
        self.thinking = chat_model.thinking

    def _return_chat_meta(self) -> None:
        model = f"{self.model_name}:{self.tag}"
        system = self.query_one(".system", TextArea).text
        system = system if system != self.model_info.get("system", "") else None
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
        if self.model_name and self.tag:
            self.select_model(f"{self.model_name}:{self.tag}")

        # Disable the model select widget if we are in edit mode.
        widget = self.query_one("#model-select", OptionList)
        widget.disabled = self.edit_mode

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_meta = next((m for m in self.models if m.model == str(model)), None)
        if model_meta:
            name, tag = (model_meta.model or "").split(":")
            self.model_name = name
            widget = self.query_one(".name", Label)
            widget.update(f"{self.model_name}")

            self.tag = tag
            widget = self.query_one(".tag", Label)
            widget.update(f"{self.tag}")

            self.bytes = model_meta["size"]
            widget = self.query_one(".size", Label)
            widget.update(f"{(self.bytes / 1.0e9):.2f} GB")

            meta = self.models_info.get(model_meta.model or "")
            self.model_info = meta  # type: ignore
            if not self.edit_mode:
                self.parameters = parse_ollama_parameters(
                    self.model_info.parameters or ""
                )
            widget = self.query_one(".parameters", TextArea)
            widget.load_text(jsonify_options(self.parameters))
            widget = self.query_one(".system", TextArea)

            # XXX Does not work as expected, there is no longer system in model_info
            widget.load_text(self.system or self.model_info.get("system", ""))

            capabilities: list[str] = self.model_info.get("capabilities", [])
            tools_supported = "tools" in capabilities
            tool_selector = self.query_one(ToolSelector)
            tool_selector.disabled = not tools_supported

            thinking_checkbox = self.query_one("#thinking-checkbox", Checkbox)
            thinking_checkbox.disabled = "thinking" not in capabilities

            if "completion" in capabilities:
                capabilities.remove("completion")  #
            if "embedding" in capabilities:
                capabilities.remove("embedding")

            caps = (
                " ".join(capabilities)
                .replace("vision", "👁️")
                .replace("tools", "🛠️")
                .replace("thinking", "🧠")
            )
            widget = self.query_one(".caps", Label)
            widget.update(caps)

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
                    with Horizontal(id="model-info"):
                        yield Label("Model:", classes="title")
                        yield Label(f"{self.model_name}", classes="name")
                        yield Label("Tag:", classes="title")
                        yield Label(f"{self.tag}", classes="tag")
                        yield Label("Size:", classes="title")
                        yield Label(f"{self.size}", classes="size")
                        yield Label("Caps:", classes="title")
                        yield Label("", classes="caps")

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
