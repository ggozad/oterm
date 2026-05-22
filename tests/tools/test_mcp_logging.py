from fastmcp.client.logging import LogMessage

from oterm.tools.mcp.logging import log_handler


async def test_log_handler_routes_by_level_to_log_lines():
    import oterm.log

    before = len(oterm.log.log_lines)

    for level, data in (
        ("debug", "D"),
        ("info", "I"),
        ("warning", "W"),
        ("error", "E"),
        ("critical", "C"),
    ):
        await log_handler(LogMessage(level=level, data=data))

    messages = [msg for _, msg in oterm.log.log_lines[before:]]
    assert "D" in messages
    assert "I" in messages
    assert "W" in messages
    assert "E" in messages
    assert "C" in messages
