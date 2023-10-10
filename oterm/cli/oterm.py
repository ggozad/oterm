import typer

from oterm.app.oterm import app

cli = typer.Typer()


@cli.command()
def salman():
    app.run()


if __name__ == "__main__":
    cli()
