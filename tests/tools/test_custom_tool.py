from oterm.tools import discover_tools


def test_discover_tools():
    """Built-in tools registered as entry points are discovered."""
    tool_defs = discover_tools()
    names = {t["name"] for t in tool_defs}
    assert "think" in names
    assert "date_time" in names
    assert "shell" in names
    for tool_def in tool_defs:
        assert tool_def["description"] != ""
