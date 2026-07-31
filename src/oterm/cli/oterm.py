import asyncio
from importlib import metadata

import typer
from rich.pretty import pprint

from oterm.config import envConfig
from oterm.log import supress_logging
from oterm.store.store import Store

cli = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})


async def upgrade_db():
    from oterm.tools import load_tools
    from oterm.tools.mcp.setup import teardown_mcp_servers

    # The 0.22.0 upgrade qualifies MCP tool names by server, which it can only
    # do while the servers are connected.
    await load_tools()
    try:
        await Store.get_store()
    finally:
        await teardown_mcp_servers()


@cli.command()
def oterm(
    version: bool = typer.Option(None, "--version", "-v"),
    upgrade: bool = typer.Option(None, "--upgrade"),
    config: bool = typer.Option(None, "--config"),
    sqlite: bool = typer.Option(None, "--db"),
    data_dir: bool = typer.Option(None, "--data-dir"),
):
    # Configure logging early to suppress all third-party package logs
    supress_logging()

    if version:
        typer.echo(f"oterm v{metadata.version('oterm')}")
        exit(0)
    if upgrade:
        asyncio.run(upgrade_db())
        exit(0)
    if sqlite:
        typer.echo(envConfig.OTERM_DATA_DIR / "store.db")
        exit(0)
    if data_dir:
        typer.echo(envConfig.OTERM_DATA_DIR)
        exit(0)
    if config:
        typer.echo(pprint(envConfig))
        exit(0)

    # Delay import to avoid sixel detection running unless necessary
    from oterm.app.oterm import app

    app.run()


if __name__ == "__main__":
    cli()
