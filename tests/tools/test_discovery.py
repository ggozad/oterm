from pydantic_ai import Tool as PydanticTool

from oterm.tools import builtin_tools, discover_tools, make_tool_def


def _hello() -> str:
    """Say hi."""
    return "hi"


class TestMakeToolDef:
    def test_wraps_callable(self):
        tool_def = make_tool_def(_hello)
        assert tool_def["name"] == "_hello"
        assert tool_def["description"] == "Say hi."
        assert isinstance(tool_def["tool"], PydanticTool)

    def test_missing_docstring_gives_empty_description(self):
        def undocumented():
            return "x"

        tool_def = make_tool_def(undocumented)
        assert tool_def["description"] == ""


class TestDiscoverTools:
    def test_discovers_registered_entry_points(self):
        tool_defs = discover_tools()
        names = {t["name"] for t in tool_defs}
        assert {"think", "date_time", "shell"}.issubset(names)

    def test_descriptions_populated_for_builtins(self):
        for tool_def in discover_tools():
            assert tool_def["description"] != ""

    def test_non_callable_entry_point_is_skipped(self, monkeypatch):
        import oterm.log
        import oterm.tools as tools_mod

        class _FakeEntryPoint:
            name = "broken"
            value = "oterm.types:ChatModel"

            def load(self):
                return 42

        monkeypatch.setattr(
            tools_mod, "entry_points", lambda group=None: [_FakeEntryPoint()]
        )
        before = len(oterm.log.log_lines)
        assert discover_tools() == []
        messages = [msg for _, msg in oterm.log.log_lines[before:]]
        assert any("not callable" in m for m in messages)

    def test_loader_error_is_logged_and_skipped(self, monkeypatch):
        import oterm.log
        import oterm.tools as tools_mod

        class _FailingEntryPoint:
            name = "exploder"
            value = "does.not:exist"

            def load(self):
                raise ImportError("kaboom")

        monkeypatch.setattr(
            tools_mod, "entry_points", lambda group=None: [_FailingEntryPoint()]
        )
        before = len(oterm.log.log_lines)
        assert discover_tools() == []
        messages = [msg for _, msg in oterm.log.log_lines[before:]]
        assert any("exploder" in m for m in messages)


def test_builtin_tools_is_a_list():
    assert isinstance(builtin_tools, list)
