from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Checkbox

from oterm.tools import available_tool_defs, available_tools


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
        self.selected = selected if selected is not None else []
        # Check if selected tools are still available from the loaded tools
        available_names = {tool_def["name"] for tool_def in available_tools()}
        self.selected = [name for name in selected if name in available_names]

    def on_mount(self) -> None:
        pass

    @on(Checkbox.Changed)
    def on_checkbox_toggled(self, ev: Checkbox.Changed):
        checkbox_name = ev.control.name
        checked = ev.value

        for server in available_tool_defs.keys():
            if server == checkbox_name:
                for tool_def in available_tool_defs[server]:
                    tool_checkbox = self.query_one(
                        f"#{server}-{tool_def['name']}", Checkbox
                    )
                    if tool_checkbox.value != checked:
                        tool_checkbox.value = checked
                return

        for tool_def in available_tools():
            if tool_def["name"] == str(checkbox_name):
                tool_name = tool_def["name"]
                if checked:
                    if tool_name not in self.selected:
                        self.selected.append(tool_name)
                else:
                    try:
                        self.selected.remove(tool_name)
                    except ValueError:
                        pass
                break

    def all_server_tools_selected(self, server: str) -> bool:
        """Check if all tools from a server are selected."""
        for tool_def in available_tool_defs[server]:
            if tool_def["name"] not in self.selected:
                return False
        return True

    def compose(self) -> ComposeResult:
        with ScrollableContainer(
            id="tool-selector",
        ):
            for server in available_tool_defs:
                with Horizontal(classes="tool-group"):
                    yield Checkbox(
                        name=server,
                        label=server,
                        tooltip=f"Select all tools from {server}",
                        classes="tool-group-select-all",
                        value=self.all_server_tools_selected(server),
                    )
                    with Vertical(classes="tools"):
                        for tool_def in available_tool_defs[server]:
                            yield Checkbox(
                                id=f"{server}-{tool_def['name']}",
                                name=tool_def["name"],
                                label=tool_def["name"],
                                tooltip=tool_def["description"],
                                value=tool_def["name"] in self.selected,
                                classes="tool",
                            )
