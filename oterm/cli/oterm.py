import asyncio
from importlib import metadata

import typer

from oterm.app.oterm import app
from oterm.config import envConfig
from oterm.store.store import Store

cli = typer.Typer()
db_store = envConfig.OTERM_DATA_DIR / "store.db"

async def upgrade_db():
    await Store.create()

async def get_journal_mode():
    res: str = await Store.get_journal_mode(db_store)
    return f"Journal mode: {res}"

async def set_journal_mode(mode: str):
    if mode not in ["WAL", "wal", "DELETE", "delete"]:
        return f"Invalid mode: {mode}"
    res: bool = await Store.set_journal_mode(db_store, mode)
    if res:
        return f"Set journal mode: {mode}"
    else:
        return f"Unable to set journal mode: {mode}"


@cli.command()
def oterm(
    version: bool = typer.Option(None, "--version", "-v", help="Return Oterm version."),
    upgrade: bool = typer.Option(None, "--upgrade", help="Upgrade the database schema."),
    sqlite: bool = typer.Option(None, "--db", help="Get database location."),
    db_get_mode: bool = typer.Option(None, "--db-get-mode", help="Get Sqlite3 journal mode."),
    db_set_mode: str = typer.Option(None, "--db-set-mode", help="Set Sqlite3 journal mode: WAL (Write Ahead Log) or DELETE (Normal behavior)."),
):
    if version:
        typer.echo(f"oterm v{metadata.version('oterm')}")
        exit(0)
    if upgrade:
        asyncio.run(upgrade_db())
        exit(0)
    if sqlite:
        typer.echo(db_store)
        exit(0)
    if db_get_mode:
        typer.echo(asyncio.run(get_journal_mode()))
        exit(0)
    if db_set_mode:
        typer.echo(asyncio.run(set_journal_mode(db_set_mode)))
        exit(0)
    app.run()


if __name__ == "__main__":
    cli()
