from importlib import metadata

import typer
from typing_extensions import Annotated

from oterm.command.create import app

cli = typer.Typer()


@cli.command()
def oterm_command(
    name: Annotated[str, typer.Argument(help="The name of the command to create")],
    version: bool = typer.Option(None, "--version", "-v"),
):
    if version:
        typer.echo(f"oterm-command v{metadata.version('oterm')}")
        exit(0)
    app.run(name)


if __name__ == "__main__":
    cli()
