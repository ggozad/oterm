from ollama import Tool
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Checkbox

from oterm.tools import available_tool_calls, available_tool_defs


class ToolSelector(Widget):
    selected: reactive[list[Tool]] = reactive([])

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        selected: list[Tool] = [],
    ) -> None:
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.selected = selected if selected is not None else []
        # Check if selected tools are still available from the loaded tools.
        available = [tool_def["tool"] for tool_def in available_tool_calls()]
        self.selected = [tool for tool in selected if tool in available]

    def on_mount(self) -> None:
        pass

    @on(Checkbox.Changed)
    def on_checkbox_toggled(self, ev: Checkbox.Changed):
        name = ev.control.name
        checked = ev.value

        for server in available_tool_defs.keys():
            if server == name:
                # We don't need to change selected,
                # it will change when the checkboxes are checked/unchecked,
                for tool_def in available_tool_defs[server]:
                    tool_checkbox = self.query_one(
                        f"#{server}-{tool_def['tool']['function']['name']}", Checkbox
                    )
                    if tool_checkbox.value != checked:
                        tool_checkbox.value = checked
                return

        for tool_def in available_tool_calls():
            if tool_def["tool"].function.name == str(name):  # type: ignore
                tool = tool_def["tool"]
                if checked:
                    self.selected.append(tool)
                else:
                    try:
                        self.selected.remove(tool)
                    except ValueError:
                        pass
                break

    def all_server_tools_selected(self, server: str) -> bool:
        """Check if all tools from a server are selected."""
        for tool_def in available_tool_defs[server]:
            if tool_def["tool"] not in self.selected:
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
                            name = tool_def["tool"]["function"]["name"]
                            yield Checkbox(
                                id=f"{server}-{name}",
                                name=name,
                                label=name,
                                tooltip=f"{tool_def['tool']['function']['description']}",
                                value=tool_def["tool"] in self.selected,
                                classes="tool",
                            )
