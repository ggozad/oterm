from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Checkbox

from oterm.tools import builtin_tools
from oterm.tools.mcp.setup import mcp_tool_meta

_BUILTIN_GROUP = "builtin"


def _all_groups() -> dict[str, list[dict]]:
    """Unified {group_name: [{'name', 'description'}, ...]} across builtin + MCP."""
    groups: dict[str, list[dict]] = {}
    if builtin_tools:
        groups[_BUILTIN_GROUP] = [
            {"name": t["name"], "description": t["description"]} for t in builtin_tools
        ]
    for server_name, metas in mcp_tool_meta.items():
        groups[server_name] = [
            {"name": m["name"], "description": m["description"]} for m in metas
        ]
    return groups


def _known_tool_names() -> set[str]:
    names = {t["name"] for t in builtin_tools}
    for metas in mcp_tool_meta.values():
        names.update(m["name"] for m in metas)
    return names


class ToolSelector(Widget):
    selected: reactive[list[str]] = reactive([])

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        selected: list[str] = [],
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        known = _known_tool_names()
        self.selected = [n for n in selected if n in known]

    def on_mount(self) -> None:
        pass

    @on(Checkbox.Changed)
    def on_checkbox_toggled(self, ev: Checkbox.Changed):
        checkbox_name = ev.control.name
        checked = ev.value
        groups = _all_groups()

        if checkbox_name in groups:
            for meta in groups[checkbox_name]:
                tool_checkbox = self.query_one(
                    f"#{checkbox_name}-{meta['name']}", Checkbox
                )
                if tool_checkbox.value != checked:
                    tool_checkbox.value = checked
            return

        for metas in groups.values():
            for meta in metas:
                if meta["name"] == str(checkbox_name):
                    if checked:
                        if meta["name"] not in self.selected:
                            self.selected.append(meta["name"])
                    else:
                        try:
                            self.selected.remove(meta["name"])
                        except ValueError:
                            pass
                    return

    def _all_group_tools_selected(self, group: str, metas: list[dict]) -> bool:
        return all(meta["name"] in self.selected for meta in metas)

    def compose(self) -> ComposeResult:
        groups = _all_groups()
        with ScrollableContainer(id="tool-selector"):
            for group, metas in groups.items():
                with Horizontal(classes="tool-group"):
                    yield Checkbox(
                        name=group,
                        label=group,
                        tooltip=f"Select all tools from {group}",
                        classes="tool-group-select-all",
                        value=self._all_group_tools_selected(group, metas),
                    )
                    with Vertical(classes="tools"):
                        for meta in metas:
                            yield Checkbox(
                                id=f"{group}-{meta['name']}",
                                name=meta["name"],
                                label=meta["name"],
                                tooltip=meta["description"],
                                value=meta["name"] in self.selected,
                                classes="tool",
                            )
