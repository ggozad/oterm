import pytest
from pydantic_ai import Tool as PydanticTool
from textual.app import App, ComposeResult
from textual.widgets import Checkbox

from oterm.app.widgets.tool_select import ToolSelector


def _tool_def(name: str):
    def fn() -> str:
        return "x"

    fn.__name__ = name
    return {
        "name": name,
        "description": f"{name} tool",
        "tool": PydanticTool(fn, takes_ctx=False),
    }


@pytest.fixture
def populated_tools(monkeypatch):
    """Inject a fake tool registry so ToolSelector has something to render."""
    import oterm.app.widgets.tool_select as sel_mod
    import oterm.tools as tools_mod

    registry = {
        "builtin": [_tool_def("date_time"), _tool_def("shell")],
        "mcp_server": [_tool_def("oracle")],
    }
    monkeypatch.setattr(tools_mod, "available_tool_defs", registry)
    monkeypatch.setattr(sel_mod, "available_tool_defs", registry)

    def _flat():
        import itertools

        return list(itertools.chain.from_iterable(registry.values()))

    monkeypatch.setattr(sel_mod, "available_tools", _flat)
    monkeypatch.setattr(tools_mod, "available_tools", _flat)
    return registry


class _Host(App):
    def __init__(self, selected: list[str] | None = None):
        super().__init__()
        self._selected = selected or []

    def compose(self) -> ComposeResult:
        yield ToolSelector(id="selector", selected=self._selected)


class TestToolSelector:
    async def test_renders_checkbox_per_server_and_tool(self, populated_tools):
        app = _Host()
        async with app.run_test() as pilot:
            selector = app.query_one(ToolSelector)
            await pilot.pause()
            names = {c.name for c in selector.query(Checkbox)}
            assert {"builtin", "mcp_server", "date_time", "shell", "oracle"}.issubset(
                names
            )

    async def test_initial_selection_reflected_in_checkboxes(self, populated_tools):
        app = _Host(selected=["date_time"])
        async with app.run_test() as pilot:
            selector = app.query_one(ToolSelector)
            await pilot.pause()
            date_time_cb = selector.query_one("#builtin-date_time", Checkbox)
            shell_cb = selector.query_one("#builtin-shell", Checkbox)
            assert date_time_cb.value is True
            assert shell_cb.value is False

    async def test_unavailable_selected_tools_filtered(self, populated_tools):
        app = _Host(selected=["date_time", "ghost"])
        async with app.run_test() as pilot:
            selector = app.query_one(ToolSelector)
            await pilot.pause()
            assert "ghost" not in selector.selected
            assert "date_time" in selector.selected

    async def test_toggling_tool_checkbox_updates_selected(self, populated_tools):
        app = _Host()
        async with app.run_test() as pilot:
            selector = app.query_one(ToolSelector)
            await pilot.pause()

            shell_cb = selector.query_one("#builtin-shell", Checkbox)
            shell_cb.value = True
            await pilot.pause()
            assert "shell" in selector.selected

            shell_cb.value = False
            await pilot.pause()
            assert "shell" not in selector.selected

    async def test_server_checkbox_toggles_all_tools(self, populated_tools):
        app = _Host()
        async with app.run_test() as pilot:
            selector = app.query_one(ToolSelector)
            await pilot.pause()

            server_cb = next(c for c in selector.query(Checkbox) if c.name == "builtin")
            server_cb.value = True
            await pilot.pause()
            assert selector.query_one("#builtin-date_time", Checkbox).value is True
            assert selector.query_one("#builtin-shell", Checkbox).value is True

    async def test_all_server_tools_selected_helper(self, populated_tools):
        app = _Host(selected=["date_time", "shell"])
        async with app.run_test() as pilot:
            selector = app.query_one(ToolSelector)
            await pilot.pause()
            assert selector.all_server_tools_selected("builtin") is True
            assert selector.all_server_tools_selected("mcp_server") is False
