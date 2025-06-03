from typing import Literal

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class Capabilities(Widget):
    caps: reactive[list[Literal["thinking"] | Literal["tools"] | Literal["vision"]]] = (
        reactive([])
    )

    def __init__(
        self,
        caps: list[Literal["thinking"] | Literal["tools"] | Literal["vision"]] = [],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.caps = caps

    def watch_caps(self) -> None:
        try:
            container = self.query_one(".capabilitiesContainer", Horizontal)
        except NoMatches:
            return
        container.remove_children()
        caps = {
            cap: f"{cap.replace('vision', '👁️').replace('tools', '🛠️').replace('thinking', '🧠')}"
            for cap in self.caps
        }
        for key, emoji in caps.items():
            label = Label(emoji, classes="capability")
            label.tooltip = key
            container.mount(label)

    def compose(self) -> ComposeResult:
        yield Horizontal(classes="capabilitiesContainer")
