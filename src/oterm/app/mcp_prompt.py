from rich.text import Text
from textual.app import ComposeResult
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
)
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList


class MCPPrompt(ModalScreen[str]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "copy", "Copy"),
    ]

    def __init__(
        self,
    ) -> None:
        super().__init__()

    def action_cancel(self) -> None:
        self.dismiss()

    def action_copy(self) -> None:
        pass

    async def on_mount(self) -> None:
        option_list = self.query_one("#mcp-prompt-select", OptionList)
        option_list.clear_options()

    def on_option_list_option_highlighted(
        self, option: OptionList.OptionHighlighted
    ) -> None:
        pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.name == "copy":
            pass
        else:
            self.dismiss()

    @staticmethod
    def prompt_option(prompt: str) -> Text:
        return Text(prompt)

    def compose(self) -> ComposeResult:
        with Container(classes="screen-container full-height"):
            with Horizontal():
                with Vertical():
                    yield Label("Available MCP prompts", classes="title")
                    yield OptionList(id="mcp-prompt-select")

                with Vertical():
                    yield Label("Customize prompt:", classes="title")

            with Horizontal(classes="button-container"):
                yield Button(
                    "Copy",
                    id="copy-btn",
                    name="copy",
                    disabled=True,
                    variant="primary",
                )
                yield Button("Cancel", name="cancel")
