from pathlib import Path

from textual.command import Hit, Hits, Provider, DiscoveryHit
from textual.screen import ModalScreen
from textual.widgets import Label, ListView, Footer, ListItem
from textual.app import ComposeResult
from textual.types import IgnoreReturnCallbackType
from textual.containers import Container


class KnowledgeSelectingCommands(Provider):
    """A command provider to open a Python file in the current working directory."""

    @property
    def _commands(self) -> tuple[tuple[str, IgnoreReturnCallbackType, str], ...]:
        return (
            (
                "Browse knowledge",
                self.app.action_browse_dirs,
                "Browse",
            ),
        )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for name, action, description in self._commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(name),
                    action,
                    help=description,
                )

    async def discover(self) -> Hits:
        for name, action, description in self._commands:
            yield DiscoveryHit(name, action, help=description)


class KnowledgeScreen(ModalScreen[Path]):
    contexts: list[Path] = []
    BINDINGS = [
        ("+", "add_context", "add context"),
        ("-", "remove_context", "remove context"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, context=[]) -> None:
        self.context = context
        super().__init__()

    def action_add_context(self) -> None:
        self.contexts.append("dummy-hehe")
        self._refresh_list_view()

    def action_remove_context(self) -> None:
        list_view = self.query_one("#contexts", ListView)
        index = list_view.index
        if index is not None and 0 <= index < len(self.contexts):
            self.contexts.pop(index)
        self._refresh_list_view()

    def action_cancel(self) -> None:
        self.dismiss()

    def on_mount(self) -> None:
        self._refresh_list_view()

    def _refresh_list_view(self) -> None:
        list_view = self.query_one("#contexts", ListView)
        index = list_view.index
        if index is None:
            index = 0
        list_view.clear()
        for context in self.contexts:
            list_view.append(ListItem(Label(context)))
        list_view.index = list_view.validate_index(index) 

    def compose(self) -> ComposeResult:
        with Container(id="context-container"):
            yield Label("Context sources", classes="title")
            yield ListView(id="contexts")
            yield Footer()
