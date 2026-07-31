import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import aiosqlite


async def qualify_mcp_tool_names(db_path: Path) -> None:
    """Rewrite MCP tool selections as `{server}_{tool}`.

    Reads the tool-to-server map from the connected MCP servers, so it must run
    after `load_tools()`. A bare name exported by several servers expands to one
    entry per server; names no connected server exports are left as they are.
    """
    from oterm.tools import builtin_tools, qualified_tool_name
    from oterm.tools.capabilities import capability_defs
    from oterm.tools.mcp.setup import mcp_tool_meta

    local_names = {t["name"] for t in builtin_tools} | {
        c["name"] for c in capability_defs
    }
    owners: dict[str, list[str]] = {}
    for server, metas in mcp_tool_meta.items():
        for meta in metas:
            if meta["name"] not in local_names:
                owners.setdefault(meta["name"], []).append(server)
    if not owners:
        return

    async with aiosqlite.connect(db_path) as connection:
        rows = await connection.execute_fetchall("SELECT id, tools FROM chat")
        for chat_id, tools_json in list(rows):
            names = json.loads(tools_json or "[]")
            qualified: list[str] = []
            for name in names:
                servers = owners.get(name)
                if servers:
                    qualified.extend(qualified_tool_name(s, name) for s in servers)
                else:
                    qualified.append(name)
            if qualified != names:
                await connection.execute(
                    "UPDATE chat SET tools = ? WHERE id = ?",
                    (json.dumps(qualified), chat_id),
                )
        await connection.commit()


upgrades: list[tuple[str, list[Callable[[Path], Awaitable[None]]]]] = [
    ("0.22.0", [qualify_mcp_tool_names]),
]
