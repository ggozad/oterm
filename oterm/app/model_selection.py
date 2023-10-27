from ast import literal_eval

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Label, OptionList, Pretty, TextArea

from oterm.ollama import OllamaAPI


class ModelDetails(Widget):
    name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: reactive[dict[str, str]] = reactive({}, layout=True)
    template: reactive[str] = reactive("")
    system: reactive[str] = reactive("")
    params: reactive[list[tuple[str, str]]] = reactive([], layout=True)

    def watch_name(self, name: str) -> None:
        try:
            widget = self.query_one(".name", Label)
            widget.update(f"Name: {self.name}")
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

    def watch_model_info(self, model_info: dict[str, str]) -> None:
        self.template = model_info.get("template", "")
        self.system = model_info.get("system", "")
        params = model_info.get("parameters", "")
        lines = params.split("\n")
        params = []
        for line in lines:
            if line:
                key, value = line.split(maxsplit=1)
                try:
                    value = literal_eval(value)
                except (SyntaxError, ValueError):
                    pass
                params.append((key, value))
        self.params = params

        try:
            widget = self.query_one(".parameters", Pretty)
            widget.update(self.params)
            widget = self.query_one(".template", TextArea)
            widget.clear()
            widget.load_text(self.template)
            widget = self.query_one(".system", TextArea)
            widget.load_text(self.system)
        except NoMatches:
            pass

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Label("Model info:", classes="title")
            yield Label("", classes="name")
            yield Label("", classes="tag")
            yield Label("", classes="size")
            yield Label("Template:", classes="title")
            yield TextArea(classes="template log")
            yield Label("System:", classes="title")
            yield TextArea("", classes="system log")
            yield Label("Parameters:", classes="title")
            yield Pretty("", classes="parameters")


class ModelSelection(ModalScreen[str]):
    api = OllamaAPI()
    models = []
    model_info: dict[str, dict] = {}

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    async def on_mount(self) -> None:
        self.models = await self.api.get_models()
        models = [model["name"] for model in self.models]
        for model in models:
            info = await self.api.get_model_info(model)
            for key in ["modelfile", "license"]:
                if key in info.keys():
                    del info[key]
            self.model_info[model] = info
        option_list = self.query_one("#model-select", OptionList)
        option_list.clear_options()
        for model in models:
            option_list.add_option(item=self.model_option(model))

    def on_option_list_option_selected(self, option: OptionList.OptionSelected) -> None:
        model = option.option.prompt
        self.dismiss(str(model))

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_meta = next((m for m in self.models if m["name"] == str(model)), None)
        model_details = self.query_one("#model-details", ModelDetails)
        if model_meta:
            name, tag = model_meta["name"].split(":")
            model_details.name = name
            model_details.tag = tag
            model_details.bytes = model_meta["size"]
            model_details.model_info = self.model_info[model_meta["name"]]

    @staticmethod
    def model_option(model: str) -> Text:
        return Text(model)

    def compose(self) -> ComposeResult:
        with Container(id="model-select-container"):
            yield Label("Select a model:", classes="title")
            with Horizontal():
                yield OptionList(id="model-select")
                yield ModelDetails(id="model-details")
