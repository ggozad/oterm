from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import DescendantBlur
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option


class ModelSelect(Vertical):
    """Input with a filtered option list for model selection."""

    DEFAULT_CSS = """
    ModelSelect {
        height: 1fr;
    }
    ModelSelect Input {
        margin-top: 1;
    }
    ModelSelect OptionList {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("down", "focus_options", "focus options", show=False),
    ]

    value: reactive[str] = reactive("", init=False)

    @dataclass
    class Changed(Message):
        """Posted when the value changes (typed or selected)."""

        value: str
        """The current value."""

    @dataclass
    class Submitted(Message):
        """Posted when a model is committed (selected from list or input blurred)."""

        value: str
        """The committed model name."""

    def __init__(
        self,
        *,
        id: str | None = None,
        placeholder: str = "Type model name...",
        disabled: bool = False,
    ) -> None:
        super().__init__(id=id, disabled=disabled)
        self._placeholder = placeholder
        self._options: list[str] = []

    def compose(self) -> ComposeResult:
        yield Input(id="model-select-input", placeholder=self._placeholder)
        yield OptionList(id="model-select-options")

    def set_options(self, options: list[str]) -> None:
        self._options = options
        self._refresh_list()

    def set_value(self, value: str) -> None:
        """Set the value programmatically without firing Submitted."""
        self.query_one("#model-select-input", Input).value = value
        self.value = value

    def action_focus_options(self) -> None:
        option_list = self.query_one("#model-select-options", OptionList)
        if option_list.option_count > 0:
            option_list.focus()

    def _refresh_list(self) -> None:
        input_value = self.query_one("#model-select-input", Input).value.casefold()
        if input_value:
            matches = [o for o in self._options if input_value in o.casefold()]
        else:
            matches = list(self._options)

        option_list = self.query_one("#model-select-options", OptionList)
        option_list.clear_options()
        option_list.add_options([Option(m) for m in matches])
        option_list.display = bool(matches)

    @on(Input.Changed, "#model-select-input")
    def _on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.value = event.value
        self._refresh_list()
        self.post_message(self.Changed(event.value))

    @on(OptionList.OptionSelected, "#model-select-options")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        value = str(event.option.prompt)
        input_widget = self.query_one("#model-select-input", Input)
        input_widget.value = value
        self.value = value
        input_widget.focus()
        self.post_message(self.Submitted(value))

    @on(DescendantBlur, "#model-select-input")
    def _on_input_blur(self, event: DescendantBlur) -> None:
        event.stop()
        value = self.query_one("#model-select-input", Input).value.strip()
        if value:
            self.post_message(self.Submitted(value))
