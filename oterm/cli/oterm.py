import asyncio
from importlib import metadata

import typer

from oterm.app.oterm import app
from oterm.store.store import Store
from oterm.utils import get_data_dir

cli = typer.Typer()


async def upgrade_db():
    await Store.create()


@cli.command()
def oterm(
    version: bool = typer.Option(None, "--version", "-v"),
    upgrade: bool = typer.Option(None, "--upgrade"),
    sqlite: bool = typer.Option(None, "--db"),
):
    if version:
        typer.echo(f"oterm v{metadata.version('oterm')}")
        exit(0)
    if upgrade:
        asyncio.run(upgrade_db())
        exit(0)
    if sqlite:
        typer.echo(get_data_dir() / "store.db")
        exit(0)
    app.run()


if __name__ == "__main__":
    cli()
