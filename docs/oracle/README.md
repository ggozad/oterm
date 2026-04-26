# Oracle — example oterm tool plugin

A minimal example of how to ship a Python package whose function is auto-discovered as an oterm tool.

The tool itself is intentionally trivial — `oracle(question)` always answers `"oterm"` — so you can focus on the packaging:

- `src/oracle/tool.py` defines the function. Its name, docstring, and type annotations are what oterm passes to the model.
- `pyproject.toml` registers the function under the `oterm.tools` entry-point group:

  ```toml
  [project.entry-points."oterm.tools"]
  oracle = "oracle.tool:oracle"
  ```

Install it into the same environment as oterm:

```bash
cd docs/oracle
uv pip install .   # or: pip install .
```

After restart, the `oracle` tool appears in the new-chat tool selector.

See the [tools guide](https://ggozad.github.io/oterm/tools/) for the full walkthrough.
