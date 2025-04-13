import json
from collections.abc import Sequence

from ollama import Options, ShowResponse
from pydantic import ValidationError
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

from oterm.ollamaclient import (
    OllamaLLM,
    jsonify_options,
    parse_format,
    parse_ollama_parameters,
)
from oterm.tools import avail_tool_defs as available_tool_defs
from oterm.types import Tool


class OtermOllamaOptions(Options):
    # Patch stop to allow for a single string.
    # This is an issue with the gemma model which has a single stop parameter.
    # Remove when fixed upstream and close #187
    stop: Sequence[str] | str | None = None

    class Config:
        extra = "forbid"


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

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "save", "Save"),
    ]

    def __init__(
        self,
        model: str = "",
        system: str = "",
        parameters: Options = Options(),
        format="",
        keep_alive: int = 5,
        edit_mode: bool = False,
        tools: list[Tool] = [],
    ) -> None:
        super().__init__()
        self.model_name, self.tag = model.split(":") if model else ("", "")
        self.system = system
        self.parameters = parameters
        self.format = format
        self.keep_alive = keep_alive
        self.edit_mode = edit_mode
        self.tools = tools

    def _return_chat_meta(self) -> None:
        model = f"{self.model_name}:{self.tag}"
        system = self.query_one(".system", TextArea).text
        system = system if system != self.model_info.get("system", "") else None
        keep_alive = int(self.query_one(".keep-alive", Input).value)
        p_area = self.query_one(".parameters", TextArea)
        try:
            parameters = OtermOllamaOptions.model_validate_json(
                p_area.text, strict=True
            ).model_dump(exclude_unset=True)
            if isinstance(parameters.get("stop"), str):
                parameters["stop"] = [parameters["stop"]]

        except ValidationError:
            self.app.notify("Error validating parameters", severity="error")
            p_area = self.query_one(".parameters", TextArea)
            p_area.styles.animate("opacity", 0.0, final_value=1.0, duration=0.5)
            return
        f_area = self.query_one(".format", TextArea)

        # Try parsing the format
        try:
            parse_format(f_area.text)
            format = f_area.text
        except Exception:
            self.app.notify("Error parsing format", severity="error")
            f_area.styles.animate("opacity", 0.0, final_value=1.0, duration=0.5)
            return

        result = json.dumps(
            {
                "name": model,
                "system": system,
                "format": format,
                "keep_alive": keep_alive,
                "parameters": parameters,
                "tools": [tool.model_dump() for tool in self.tools],
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

    @on(Checkbox.Changed)
    def on_tool_toggled(self, ev: Checkbox.Changed):
        tool_name = ev.control.label
        checked = ev.value
        for tool_def in available_tool_defs:
            if tool_def["tool"].function.name == str(tool_name):  # type: ignore
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

            # Deduce from the model's template if the model is tool-capable.
            tools_supported = ".Tools" in self.model_info["template"]
            widgets = self.query(".tool")
            for widget in widgets:
                widget.disabled = not tools_supported
                if not tools_supported:
                    widget.value = False  # type: ignore

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
