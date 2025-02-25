from pathlib import Path

tcss = ""
with open(Path(__file__).parent / "oterm.tcss") as f:
    tcss = f.read()
