from mcp.types import LoggingMessageNotificationParams

from oterm.tools.mcp.logging import Logger


async def test_logger_routes_by_level_to_log_lines():
    import oterm.log

    logger = Logger()
    before = len(oterm.log.log_lines)

    for level, data in (
        ("debug", "D"),
        ("info", "I"),
        ("warning", "W"),
        ("error", "E"),
        ("critical", "C"),
    ):
        await logger(
            LoggingMessageNotificationParams(level=level, data=data)  # type: ignore[arg-type]
        )

    messages = [msg for _, msg in oterm.log.log_lines[before:]]
    assert "D" in messages
    assert "I" in messages
    assert "W" in messages
    assert "E" in messages
    assert "C" in messages
