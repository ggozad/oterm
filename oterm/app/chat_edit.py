import json
from ast import literal_eval

from ollama import Options
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, OptionList

from oterm.app.widgets.text_area import TextArea
from oterm.ollamaclient import OllamaLLM


class ChatEdit(ModalScreen[str]):
    models = []
    models_info: dict[str, dict] = {}

    model_name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: dict[str, str] = {}
    system: reactive[str] = reactive("")
    params: reactive[Options] = reactive({})
    json_format: reactive[bool] = reactive(False)
    edit_mode: reactive[bool] = reactive(False)
    last_highlighted_index = None
    keep_alive: reactive[int] = reactive(5)

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "save", "Save"),
    ]

    def _return_chat_meta(self) -> None:
        model = f"{self.model_name}:{self.tag}"
        system = self.query_one(".system", TextArea).text
        system = system if system != self.model_info.get("system", "") else None
        jsn = self.query_one(".json-format", Checkbox).value
        keep_alive = int(self.query_one(".keep-alive", Input).value)
        result = json.dumps(
            {
                "name": model,
                "system": system,
                "format": "json" if jsn else "",
                "keep_alive": keep_alive,
            }
        )
        self.dismiss(result)

    def _parse_model_params(self, parameter_text: str) -> Options:
        lines = parameter_text.split("\n")
        params = Options()
        for line in lines:
            if line:
                key, value = line.split(maxsplit=1)
                try:
                    value = literal_eval(value)
                except (SyntaxError, ValueError):
                    pass
                if params.get(key):
                    if not isinstance(params[key], list):
                        params[key] = [params[key], value]
                    else:
                        params[key].append(value)
                else:
                    params[key] = value
        return params

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
            try:
                widget = self.query_one(".parameters", TextArea)
                widget.load_text(json.dumps(self.params, indent=2))
                widget = self.query_one(".system", TextArea)
                widget.load_text(self.system or self.model_info.get("system", ""))
            except NoMatches:
                pass

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

    def watch_keep_alive(self, keep_alive: int) -> None:
        try:
            widget = self.query_one(".keep-alive", Input)
            widget.value = str(keep_alive)
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
                    yield TextArea("", classes="parameters log", language="json")
                    with Horizontal():
                        yield Checkbox(
                            "JSON output",
                            value=False,
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
