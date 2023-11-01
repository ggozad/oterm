import json
from ast import literal_eval

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList, Pretty, TextArea

from oterm.ollama import OllamaAPI


class ModelSelection(ModalScreen[str]):
    api = OllamaAPI()
    models = []
    models_info: dict[str, dict] = {}

    name: reactive[str] = reactive("")
    tag: reactive[str] = reactive("")
    bytes: reactive[int] = reactive(0)
    model_info: reactive[dict[str, str]] = reactive({}, layout=True)
    template: reactive[str] = reactive("")
    system: reactive[str] = reactive("")
    params: reactive[list[tuple[str, str]]] = reactive([], layout=True)

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
            self.models_info[model] = info
        option_list = self.query_one("#model-select", OptionList)
        option_list.clear_options()
        for model in models:
            option_list.add_option(item=self.model_option(model))

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        model = option.option.prompt
        model_meta = next((m for m in self.models if m["name"] == str(model)), None)
        if model_meta:
            name, tag = model_meta["name"].split(":")
            self.name = name
            self.tag = tag
            self.bytes = model_meta["size"]

            self.model_info = self.models_info[model_meta["name"]]

        # Now that there is a model selected we can create the chat.
        create_button = self.query_one("#create-btn", Button)
        create_button.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "create":
            model = f"{self.name}:{self.tag}"
            template = self.query_one(".template", TextArea).text
            template = (
                template if template != self.model_info.get("template", "") else None
            )
            system = self.query_one(".system", TextArea).text
            system = system if system != self.model_info.get("system", "") else None
            result = json.dumps({"name": model, "template": template, "system": system})
            self.dismiss(result)
        else:
            self.dismiss()

    @staticmethod
    def model_option(model: str) -> Text:
        return Text(model)

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
                    yield Label("Template:", classes="title")
                    yield TextArea(classes="template log")
                    yield Label("System:", classes="title")
                    yield TextArea("", classes="system log")
                    yield Label("Parameters:", classes="title")
                    yield Pretty("", classes="parameters")

            with Horizontal(classes="button-container"):
                yield Button(
                    "Create",
                    id="create-btn",
                    name="create",
                    disabled=True,
                    variant="primary",
                )
                yield Button("Cancel", name="cancel")
