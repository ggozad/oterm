# Tools

`oterm` supports integration with tools. Tools are special "functions" that can provide external information to the LLM model that it does not otherwise have access to.

With tools, you can provide the model with access to the web, run shell commands, perform RAG and more.

[Use existing Model Context Protocol servers](../mcp/index.md)

or

[create your own custom tools](#custom-tools-with-oterm).

### Custom tools with oterm

You can create your own custom tools and integrate them with `oterm` using Python [entry points](https://packaging.python.org/en/latest/specifications/entry-points/).

#### Create a python package

Create a python package that exports a callable function. The function's name, docstring, and type annotations are used to generate the tool definition for the model.

Here is an [example](https://github.com/ggozad/oterm/tree/main/docs/oracle){:target="_blank"} of a simple tool that implements an Oracle:

```python
def oracle(question: str) -> str:
    """Function to return the Oracle's answer to any question.

    Args:
        question: The question to ask.
    """
    return "oterm"
```

#### Register the tool as an entry point

In your package's `pyproject.toml`, register the tool under the `oterm.tools` entry-point group:

```toml
[project.entry-points."oterm.tools"]
oracle = "oracle.tool:oracle"
```

#### Install and use

Install the package in the same environment where `oterm` is installed:

```bash
cd oracle
uv pip install . # or pip install .
```

That's it! `oterm` discovers all tools registered under the `oterm.tools` entry-point group at startup. You can now select the tool when creating or editing a chat.

### Built-in tools

The following tools are built-in to `oterm` and available by default:

* `think` - provides the model with a way to think about a question before answering it. This is useful for complex questions that require reasoning. Use it for adding a "thinking" step to the model's response.
* `date_time` - provides the current date and time in ISO format.
* `shell` - allows you to run shell commands and use the output as input to the model. Obviously this can be dangerous, so use with caution.

### Tool calls in the chat

When the model invokes a tool during a response, `oterm` renders the call inline as a collapsible entry between any "thoughts" and the response itself:

```
▸ tool call: search_repo
```

Click the line (or its arrow) to expand it. The expanded body shows:

* `args:` — the arguments the model passed to the tool. Dictionaries and JSON-encoded strings are pretty-printed with syntax highlighting; plain strings are shown verbatim and truncated if very long.
* `result:` — the value the tool returned, formatted the same way. Appears once the tool has finished.

Click again to collapse. Multiple calls within the same turn each get their own entry.
