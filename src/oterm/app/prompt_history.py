from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList


class PromptHistory(ModalScreen[str]):
    history: list[str] = []
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, history=[]) -> None:
        self.history = history
        super().__init__()

    def action_cancel(self) -> None:
        self.dismiss()

    def on_mount(self) -> None:
        option_list = self.query_one("#prompt-history", OptionList)
        option_list.clear_options()
        for prompt in self.history:
            option_list.add_option(option=Text(prompt))

    def on_option_list_option_selected(self, option: OptionList.OptionSelected) -> None:
        self.dismiss(str(option.option.prompt))

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container full-height"):
            yield Label("Prompt history", classes="title")
            yield OptionList(id="prompt-history")
