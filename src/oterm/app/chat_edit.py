import json

from ollama import Options
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
)
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList, TextArea

from oterm.ollamaclient import OllamaLLM, parse_ollama_parameters
from oterm.tools import Tool
from oterm.tools import available as available_tool_defs


class ChatEdit(ModalScreen[str]):
    models = []
    models_info: dict[str, dict] = {}

    model_name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: dict[str, str] = {}
    system: reactive[str] = reactive("")
    parameters: reactive[Options] = reactive({})
    json_format: reactive[bool] = reactive(False)
    keep_alive: reactive[int] = reactive(5)
    last_highlighted_index = None
    tools: reactive[list[Tool]] = reactive([])
    edit_mode: reactive[bool] = reactive(False)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "save", "Save"),
    ]

    def __init__(
        self,
        model: str = "",
        system: str = "",
        parameters: Options = {},
        keep_alive: int = 5,
        json_format: bool = False,
        edit_mode: bool = False,
        tools: list[Tool] = [],
    ) -> None:
        super().__init__()
        self.model_name, self.tag = model.split(":") if model else ("", "")
        self.system = system
        self.parameters = parameters
        self.keep_alive = keep_alive
        self.json_format = json_format
        self.edit_mode = edit_mode
        self.tools = tools

    def _return_chat_meta(self) -> None:
        model = f"{self.model_name}:{self.tag}"
        system = self.query_one(".system", TextArea).text
        system = system if system != self.model_info.get("system", "") else None
        jsn = self.query_one(".json-format", Checkbox).value
        keep_alive = int(self.query_one(".keep-alive", Input).value)
        p_area = self.query_one(".parameters", TextArea)
        try:
            parameters = json.loads(p_area.text)
            if not isinstance(parameters, dict):
                raise TypeError("Parameters must be a JSON object.")
            if not set(parameters.keys()).issubset(set(Options.__annotations__.keys())):
                raise TypeError(
                    f"Parameters must be a subset of {Options.__annotations__.keys()}"
                )
        except (json.JSONDecodeError, TypeError):
            p_area = self.query_one(".parameters", TextArea)
            p_area.styles.animate("opacity", 0.0, final_value=1.0, duration=0.5)
            return

        result = json.dumps(
            {
                "name": model,
                "system": system,
                "format": "json" if jsn else "",
                "keep_alive": keep_alive,
                "parameters": parameters,
                "tools": self.tools
            }
        )
        self.dismiss(result)

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
        self.models = OllamaLLM.list()["models"]
        models = [model["name"] for model in self.models]
        for model in models:
            info = dict(OllamaLLM.show(model))
            for key in ["modelfile", "license"]:
                if key in info.keys():
                    del info[key]
            self.models_info[model] = info
        option_list = self.query_one("#model-select", OptionList)
        option_list.clear_options()
        for model in models:
            option_list.add_option(item=self.model_option(model))
        option_list.highlighted = self.last_highlighted_index
        if self.model_name and self.tag:
            self.select_model(f"{self.model_name}:{self.tag}")

        # Disable the model select widget if we are in edit mode.
        widget = self.query_one("#model-select", OptionList)
        widget.disabled = self.edit_mode

    def on_option_list_option_selected(self, option: OptionList.OptionSelected) -> None:
        self._return_chat_meta()

    @on(Checkbox.Changed)
    def on_tool_toggled(self, ev: Checkbox.Changed):
        tool_name = ev.control.label
        checked = ev.value
        for tool_def in available_tool_defs:
            if tool_def["tool"]["function"]["name"] == str(tool_name):
                tool = tool_def["tool"]
                if checked:
                    self.tools.append(tool)
                else:
                    self.tools.remove(tool)
                break

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_meta = next((m for m in self.models if m["name"] == str(model)), None)
        if model_meta:
            name, tag = model_meta["name"].split(":")
            self.model_name = name
            widget = self.query_one(".name", Label)
            widget.update(f"{self.model_name}")

            self.tag = tag
            widget = self.query_one(".tag", Label)
            widget.update(f"{self.tag}")

            self.bytes = model_meta["size"]
            widget = self.query_one(".size", Label)
            widget.update(f"{(self.bytes / 1.0e9):.2f} GB")

            self.model_info = self.models_info[model_meta["name"]]
            if not self.edit_mode:
                self.parameters = parse_ollama_parameters(
                    self.model_info.get("parameters", "")
                )
            widget = self.query_one(".parameters", TextArea)
            widget.load_text(json.dumps(self.parameters, indent=2))
            widget = self.query_one(".system", TextArea)
            widget.load_text(self.system or self.model_info.get("system", ""))

            # Deduce from the model's template if the model is tool-capable.
            tools_supported = ".Tools" in self.model_info["template"]
            widgets = self.query(".tool")
            for widget in widgets:
                widget.disabled = not tools_supported
                if not tools_supported:
                    widget.value = False # type: ignore

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
        with Container(id="edit-chat-container"):
            with Horizontal():
                with Vertical():
                    with Horizontal(id="model-info"):
                        yield Label("Model:", classes="title")
                        yield Label(f"{self.model_name}", classes="name")
                        yield Label("Tag:", classes="title")
                        yield Label(f"{self.tag}", classes="tag")
                        yield Label("Size:", classes="title")
                        yield Label(f"{self.size}", classes="size")

                    yield OptionList(id="model-select")
                    yield Label("Tools:", classes="title")
                    with ScrollableContainer(id="tool-list"):
                        for tool_def in available_tool_defs:
                            yield Checkbox(
                                label=f"{tool_def['tool']['function']['name']}",
                                tooltip=f"{tool_def['tool']['function']['description']}",
                                value=tool_def["tool"] in self.tools,
                                classes="tool",
                            )

                with Vertical():
                    yield Label("System:", classes="title")
                    yield TextArea(self.system, classes="system log")
                    yield Label("Parameters:", classes="title")
                    yield TextArea(
                        json.dumps(self.parameters, indent=2),
                        classes="parameters log",
                        language="json",
                    )
                    with Horizontal():
                        yield Checkbox(
                            "JSON",
                            value=self.json_format,
                            classes="json-format",
                            button_first=False,
                        )
                        with Horizontal():
                            yield Label(
                                "Keep-alive (min)", classes="title keep-alive-label"
                            )
                            yield Input(classes="keep-alive", value="5")

            with Horizontal(classes="button-container"):
                yield Button(
                    "Save",
                    id="save-btn",
                    name="save",
                    disabled=True,
                    variant="primary",
                )
                yield Button("Cancel", name="cancel")
