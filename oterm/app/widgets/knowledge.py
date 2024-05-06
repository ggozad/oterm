from pathlib import Path
from typing import Iterable

from textual.command import Hit, Hits, Provider, DiscoveryHit
from textual.screen import ModalScreen
from textual.widgets import Label, ListView, Footer, ListItem, DirectoryTree, Tree, Input
from textual.app import ComposeResult
from textual.types import IgnoreReturnCallbackType, DirEntry
from textual.containers import Container, Vertical
from textual import on
from rich.text import Text

CONTEXT_DIRECTORY = ".rtfm"

class KnowledgeSelectingCommands(Provider):
    """A command provider to open a Python file in the current working directory."""

    @property
    def _commands(self) -> tuple[tuple[str, IgnoreReturnCallbackType, str], ...]:
        return (
            (
                "Manage context",
                self.app.action_browse_dirs,
                "Manage context sources which will be matched against user queries",
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


class KnowledgeScreen(ModalScreen[list[Path]]):
    contexts: set[Path] = []
    BINDINGS = [
        ("+", "add_context", "add context"),
        ("-", "remove_context", "remove context"),
        ("escape", "close", "close"),
    ]

    def __init__(self, context=[]) -> None:
        self.context = context
        super().__init__()

    def action_add_context(self) -> None:
        async def on_context_selected(context_path: Path) -> None:
            if context_path not in self.contexts:
                self.contexts.append(context_path)
            self._refresh_list_view()

        screen = ContextSelect()
        self.app.push_screen(screen, on_context_selected)

    def action_remove_context(self) -> None:
        list_view = self.query_one("#contexts", ListView)
        index = list_view.index
        if index is not None and 0 <= index < len(self.contexts):
            self.contexts.pop(index)
        self._refresh_list_view()

    def action_close(self) -> None:
        self.dismiss(self.contexts)

    def on_mount(self) -> None:
        self._refresh_list_view()

    def _refresh_list_view(self) -> None:
        list_view = self.query_one("#contexts", ListView)
        index = list_view.index
        if index is None:
            index = 0
        list_view.clear()
        for context in self.contexts:
            list_view.append(ListItem(Label(str(context))))
        list_view.index = list_view.validate_index(index)

    def compose(self) -> ComposeResult:
        with Container(id="context-container"):
            yield Label("Context sources", classes="title")
            yield ListView(id="contexts")
            yield Footer()


class ContextSelect(ModalScreen[Path]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    def action_cancel(self) -> None:
        self.dismiss()

    async def on_mount(self) -> None:
        dt: ContextDirectoryTree = self.query_one(ContextDirectoryTree)
        dt.show_guides = False
        dt.focus()

    @on(DirectoryTree.DirectorySelected)
    async def on_directory_selected(self, event: DirectoryTree.FileSelected):
        if event.path.stem == CONTEXT_DIRECTORY:
            self.dismiss(event.path)

    @on(Input.Changed)
    async def on_root_changed(self, ev: Input.Changed) -> None:
        dt = self.query_one(ContextDirectoryTree)
        path = Path(ev.value)
        if not path.exists() or not path.is_dir():
            return
        dt.path = path

    def compose(self) -> ComposeResult:
        with Container(id="context-select-container"):
            with Vertical(id="context-directory-tree"):
                yield Label("Select context source:", classes="title")
                yield Label("Root:")
                yield Input(Path("./").resolve().as_posix())
                yield ContextDirectoryTree("./")
                yield Footer()


class ContextDirectoryTree(DirectoryTree):
    def render_label(
        self,
        node,
        base_style,
        style,
    ):
        rendered = super().render_label(node, base_style, style)

        path = node.data.path
        if path.is_dir():
            contents = [subpath.name for subpath in path.iterdir()]
            if CONTEXT_DIRECTORY in contents or path.stem == CONTEXT_DIRECTORY:
                rendered.stylize("blue")
        return rendered

    def filter_paths(self, paths: Iterable[Path]):
        return list(paths)
