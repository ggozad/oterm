import json
import re
from ast import literal_eval
from typing import Any

import ollama
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, HorizontalScroll, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Label, OptionList, Pretty, Input, Select

from oterm.app.widgets.text_area import TextArea
from oterm.ollama import OllamaLLM


class ChatEdit(ModalScreen[str]):
    models = []
    models_info: dict[str, dict] = {}

    int_value_pattern = f"\d+"

    keep_alive_value_default = 5
    keep_alive_unit_default = "m"
    keep_alive_default = f"{keep_alive_value_default}{keep_alive_unit_default}"
    keep_alive_units = ["s","m","h","d"]
    keep_alive_unit_pattern = rf"{'|'.join(keep_alive_units)}"
    keep_alive_pattern = rf"({int_value_pattern})({keep_alive_unit_pattern})"

    model_options_default = {
        "num_ctx": 2048,
        "temperature": 0.8,
        "seed": 0,
        "top_k": 40,
        "top_p": 0.9
    }

    model_name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: dict[str, str] = {}
    system: reactive[str] = reactive("")
    params: reactive[list[tuple[str, str]]] = reactive([])
    params_dict: reactive[dict] = reactive({})
    json_format: reactive[bool] = reactive(False)
    edit_mode: reactive[bool] = reactive(False)
    last_highlighted_index = None

    keep_alive_value: reactive[int] = reactive(keep_alive_value_default)
    keep_alive_unit: reactive[str] = reactive(keep_alive_unit_default)
    keep_alive: reactive[str] = reactive("")

    model_num_ctx: reactive[int] = reactive(model_options_default["num_ctx"])
    model_temperature: reactive[float] = reactive(model_options_default["temperature"])
    model_seed: reactive[int] = reactive(model_options_default["seed"])
    model_top_k: reactive[int] = reactive(model_options_default["top_k"])
    model_top_p: reactive[float] = reactive(model_options_default["top_p"])
    model_options: reactive[dict] = reactive({})

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "save", "Save"),
        ("ctrl+r", "reset", "Reset"),
    ]

    def _return_chat_meta(self) -> None:
        model = f"{self.model_name}:{self.tag}"
        system = self.query_one(".system", TextArea).text
        system = system if system != self.model_info.get("system", "") else None
        jsn = self.query_one(".json-format", Checkbox).value

        keep_alive_value = self.query_one(".keep-alive-value", Input).value
        keep_alive_unit = self.query_one(".keep-alive-unit", Select).value
        keep_alive = f"{keep_alive_value}{keep_alive_unit}"
        if keep_alive == self.keep_alive_default or not re.fullmatch(self.keep_alive_pattern, keep_alive): keep_alive = None

        model_options = {}

        model_num_ctx = self.query_one(".model-num-ctx", Input).value
        if model_num_ctx != "": model_options["num_ctx"] = int(model_num_ctx)
        model_temperature = self.query_one(".model-temperature", Input).value
        if model_temperature != "": model_options["temperature"] = float(model_temperature)
        model_seed = self.query_one(".model-seed", Input).value
        if model_seed != "": model_options["seed"] = int(model_seed)
        model_top_k = self.query_one(".model-top-k", Input).value
        if model_top_k != "": model_options["top_k"] = int(model_top_k)
        model_top_p = self.query_one(".model-top-p", Input).value
        if model_top_p != "": model_options["top_p"] = float(model_top_p)

        result = json.dumps(
            {
                "name": model,
                "system": system,
                "format": "json" if jsn else "",
                "keep_alive": keep_alive,
                "model_options": model_options,
            }
        )
        self.dismiss(result)

    def _reset_options(self) -> None:
        self.system = self.model_info.get("system", "") 
        self.jsn = ""

        self.keep_alive_value = self.keep_alive_value_default
        self.keep_alive_unit = self.keep_alive_unit_default
        self.keep_alive = None

        self.model_options = {}

        self.model_num_ctx = ""
        self.model_temperature = ""
        self.model_seed = ""
        self.model_top_k = ""
        self.model_top_p = ""

    def _parse_model_params(self, parameter_text: str) -> list[tuple[str, Any]]:
        lines = parameter_text.split("\n")
        params = []
        for line in lines:
            if line:
                key, value = line.split(maxsplit=1)
                try:
                    value = literal_eval(value)
                except (SyntaxError, ValueError):
                    pass
                params.append((key, value))
        return params

    def action_cancel(self) -> None:
        self.dismiss()

    def action_save(self) -> None:
        self._return_chat_meta()

    def action_reset(self) -> None:
        self._reset_options()

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

    def on_option_list_option_selected(self, option: OptionList.OptionSelected) -> None:
        self._return_chat_meta()

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_meta = next((m for m in self.models if m["name"] == str(model)), None)
        if model_meta:
            name, tag = model_meta["name"].split(":")
            self.model_name = name
            self.tag = tag
            self.bytes = model_meta["size"]

            self.model_info = self.models_info[model_meta["name"]]
            self.params = self._parse_model_params(
                self.model_info.get("parameters", "")
            )
            self.params_dict = dict(self.params)
            try:
                widget = self.query_one(".parameters", Pretty)
                widget.update(self.params)
                widget = self.query_one(".system", TextArea)
                widget.load_text(self.system or self.model_info.get("system", ""))

                widget = self.query_one(".keep-alive-value", Input)
                if self.keep_alive_value != self.keep_alive_value_default:
                    widget.placeholder = str(self.keep_alive_value_default)

                widget = self.query_one(".keep-alive-unit", Select)
                if self.keep_alive_unit != self.keep_alive_unit_default:
                    widget.value = self.keep_alive_unit_default

                for model_option in self.model_options_default:
                    selector = f".model-{model_option.replace('_', '-')}"
                    widget = self.query_one(selector, Input)
                    if model_option in self.params_dict and self.params_dict[model_option] != self.model_options_default[model_option]:
                        widget.placeholder = str(self.params_dict[model_option])
                    else:
                        widget.placeholder = str(self.model_options_default[model_option])
            except NoMatches:
                pass

        # Now that there is a model selected we can save the chat.
        save_button = self.query_one("#save-btn", Button)
        save_button.disabled = False
        ChatEdit.last_highlighted_index = option.option_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "save":
            self._return_chat_meta()
        elif event.button.name == "reset":
            self._reset_options()
        else:
            self.dismiss()

    @staticmethod
    def model_option(model: str) -> Text:
        return Text(model)

    def watch_name(self, name: str) -> None:
        try:
            widget = self.query_one(".name", Label)
            widget.update(f"Name: {self.model_name}")
        except NoMatches:
            pass

    def watch_tag(self, tag: str) -> None:
        try:
            widget = self.query_one(".tag", Label)
            widget.update(f"Tag: {self.tag}")
        except NoMatches:
            pass

    def watch_bytes(self, size: int) -> None:
        try:
            widget = self.query_one(".size", Label)
            widget.update(f"Size: {(self.bytes / 1.0e9):.2f} GB")
        except NoMatches:
            pass

    def watch_system(self, system: str) -> None:
        try:
            widget = self.query_one(".system", TextArea)
            widget.load_text(system)
        except NoMatches:
            pass

    def watch_json_format(self, jsn: bool) -> None:
        try:
            widget = self.query_one(".json-format", Checkbox)
            widget.value = jsn
        except NoMatches:
            pass

    def watch_keep_alive(self, keep_alive: str) -> None:
        try:
            match = re.fullmatch(self.keep_alive_pattern, keep_alive or "")
            if match:
                self.keep_alive_value = match.group(1)
                self.keep_alive_unit = match.group(2)
        except NoMatches:
            pass

    def watch_keep_alive_value(self, keep_alive_value: int) -> None:
        try:
            widget = self.query_one(".keep-alive-value", Input)
            if keep_alive_value != self.keep_alive_value_default:
                widget.value = str(keep_alive_value)
            else: 
                widget.value = ""
        except NoMatches:
            pass

    def watch_keep_alive_unit(self, keep_alive_unit: str) -> None:
        try:
            widget = self.query_one(".keep-alive-unit", Select)
            if keep_alive_unit != self.keep_alive_unit_default:
                widget.value = keep_alive_unit
            else: 
                widget.value = self.keep_alive_unit_default
        except NoMatches: 
            pass

    def watch_model_options(self, model_options: dict) -> None:
        try:
            if model_options != {}:
                for k, v in model_options.items():
                    setattr(self, f"model_{k}", v)
        except NoMatches:
            pass

    def watch_model_num_ctx(self, model_num_ctx: int) -> None:
        try:
            widget = self.query_one(".model-num-ctx", Input)
            if str(model_num_ctx) != widget.placeholder:
                widget.value = str(model_num_ctx)
            else:
                widget.value = ""
        except NoMatches:
            pass

    def watch_model_temperature(self, model_temperature: float) -> None:
        try:
            widget = self.query_one(".model-temperature", Input)
            if str(model_temperature) != widget.placeholder:
                widget.value = str(model_temperature)
            else: 
                widget.value = ""
        except NoMatches:
            pass

    def watch_model_seed(self, model_seed: int) -> None:
        try:
            widget = self.query_one(".model-seed", Input)
            if str(model_seed) != widget.placeholder:
                widget.value = str(model_seed)
            else: 
                widget.value = ""
        except NoMatches:
            pass

    def watch_model_top_k(self, model_top_k: int) -> None:
        try:
            widget = self.query_one(".model-top-k", Input)
            if str(model_top_k) != widget.placeholder:
                widget.value = str(model_top_k)
            else: 
                widget.value = ""
        except NoMatches:
            pass

    def watch_model_top_p(self, model_top_p: float) -> None:
        try:
            widget = self.query_one(".model-top-p", Input)
            if str(model_top_p) != widget.placeholder:
                widget.value = str(model_top_p)
            else: 
                widget.value = ""
        except NoMatches:
            pass

    def watch_edit_mode(self, edit_mode: bool) -> None:
        try:
            widget = self.query_one("#model-select", OptionList)
            widget.disabled = edit_mode
        except NoMatches:
            pass

    def compose(self) -> ComposeResult:
        with Container(id="model-select-container"):
            yield Label("Select a model:", classes="title")
            with Horizontal():
                with Vertical():
                    yield OptionList(id="model-select")
                    with Vertical(id="model-details"):
                        yield Label("Model info:", classes="title")
                        yield Label("", classes="name")
                        yield Label("", classes="tag")
                        yield Label("", classes="size")
                with Vertical():
                    yield Label("System:", classes="title")
                    yield TextArea("", classes="system log")
                    yield Label("Parameters:", classes="title")
                    yield Pretty("", classes="parameters")
                    yield Label("Format:", classes="title")
                    yield Checkbox("JSON output", value=False, classes="json-format")
                    with VerticalScroll(id="model-settings"):
                        with HorizontalScroll(id="model-keep-alive"):
                            yield Label("Keep-Alive:", classes="title")
                            yield Input(
                                "",
                                type="integer",
                                max_length=4,
                                restrict=self.int_value_pattern,
                                classes="keep-alive-value",
                                placeholder=str(self.keep_alive_value_default),
                            )
                            yield Select.from_values(
                                self.keep_alive_units,
                                allow_blank=False,
                                classes="keep-alive-unit",
                                value=self.keep_alive_unit,
                            )
                        with Vertical(id="model-options"):
                            yield Label("Options:", classes="title model-options-label")
                            with Horizontal():
                                yield Label("num_ctx:", classes="model-num-ctx-label")
                                yield Input(
                                    "",
                                    type="integer",
                                    max_length=8,
                                    restrict=self.int_value_pattern,
                                    classes="model-num-ctx",
                                    placeholder=str(self.model_options_default["num_ctx"]),
                                )
                            with Horizontal():
                                yield Label("temperature:", classes="model-temperature-label")
                                yield Input(
                                    "",
                                    type="number",
                                    max_length=6,
                                    classes="model-temperature",
                                    placeholder=str(self.model_options_default["temperature"]),
                                )
                            with Horizontal():
                                yield Label("seed:", classes="model-seed-label")
                                yield Input(
                                    "",
                                    type="integer",
                                    max_length=4,
                                    restrict=self.int_value_pattern,
                                    classes="model-seed",
                                    placeholder=str(self.model_options_default["seed"]),
                                )
                            with Horizontal():
                                yield Label("top_k:", classes="model-top-k-label")
                                yield Input(
                                    "",
                                    type="integer",
                                    max_length=4,
                                    restrict=self.int_value_pattern,
                                    classes="model-top-k",
                                    placeholder=str(self.model_options_default["top_k"]),
                                )
                            with Horizontal():
                                yield Label("top_p:", classes="model-top-p-label")
                                yield Input(
                                    "",
                                    type="number",
                                    max_length=6,
                                    classes="model-top-p",
                                    placeholder=str(self.model_options_default["top_p"]),
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
                yield Button("Reset", name="reset", variant="warning")
