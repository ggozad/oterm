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
* `generate_image` - generates an image from a text prompt using an Ollama image-generation model (e.g. `x/z-image-turbo`, `x/flux2-klein`). The default model is `x/z-image-turbo`; override it for a single call via the tool's `model` argument or globally via the `OTERM_OLLAMA_IMAGE_MODEL` environment variable. The image renders inline in the chat. Requires an Ollama server with an image-capable model installed; the host LLM (any provider) writes the prompt and calls the tool.

### Capabilities

Alongside tools, `oterm` offers [pydantic-ai capabilities](https://ai.pydantic.dev/capabilities/overview/) in the tool selector, under the `capabilities` group:

* `web_search` - searches the web. Uses the provider's native web search when available (e.g. Anthropic, OpenAI), and falls back to DuckDuckGo for providers without one (e.g. Ollama).
* `web_fetch` - fetches the contents of a URL, using the provider's native URL fetching when available.
* `memory` - gives the model a persistent memory notebook, shared across all chats and stored in `memory.db` in the oterm data directory. The model reads, writes and searches it with dedicated tools.
* `filesystem` - lets the model read, write and search files under the directory `oterm` was started from. Paths outside it are rejected, and sensitive files (`.git`, `.env`, keys, secrets) are read-only.
* `speak` - reads the response aloud as it streams, through [piper](https://github.com/OHF-Voice/piper1-gpl). The voice is GLaDOS. There is no setting to change it. [pydantic-ai-tts](https://pypi.org/project/pydantic-ai-tts/) can synthesize 175 catalogue voices. You get the one from the enrichment center. Run `uvx "oterm[speak]"`, which requires Python 3.11 or newer and brings `piper-tts` (GPL-3.0) along with it. The capability appears in the selector only once it is installed, so if you cannot see it, it is not there. On the first response a voice model downloads and nothing whatsoever appears to happen. That is expected. Everything here is expected. `oterm` also sets `ORT_DISABLE_TELEMETRY=1` before onnxruntime loads, unless you have already set it yourself. The Enrichment Center gathers quite enough data without help.

### Tool calls in the chat

When the model invokes a tool during a response, `oterm` renders the call inline as a collapsible entry between any "thoughts" and the response itself:

```
▸ tool call: search_repo
```

Click the line (or its arrow) to expand it. The expanded body shows:

* `args:` — the arguments the model passed to the tool. Dictionaries and JSON-encoded strings are pretty-printed with syntax highlighting; plain strings are shown verbatim and truncated if very long.
* `result:` — the value the tool returned, formatted the same way. Appears once the tool has finished.

Click again to collapse. Multiple calls within the same turn each get their own entry.
