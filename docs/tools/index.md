# Tools

`oterm` supports integration with tools. Tools are special "functions" that can provide external information to the LLM model that it does not otherwise have access to.

With tools, you can provide the model with access to the web, run shell commands, perform RAG and more.

[Use existing Model Context Protocol servers](../mcp/index.md)

or

[create your own custom tools](#custom-tools-with-oterm).

### Custom tools with oterm

You can create your own custom tools and integrate them with `oterm`.

#### Create a python package.

You will need to create a python package that exports a `Tool` definition as well as a *callable* function that will be called when the tool is invoked.

Here is an [example](https://github.com/ggozad/oterm/tree/main/docs/oracle){:target="_blank"} of a simple tool that implements an Oracle. The tool is defined in the `oracle` package which exports the `OracleTool` tool definition and an `oracle` callable function.

```python
from ollama import Tool

OracleTool = Tool(
    type="function",
    function=Tool.Function(
        name="oracle",
        description="Function to return the Oracle's answer to any question.",
        parameters=Tool.Function.Parameters(
            type="object",
            properties={
                "question": Tool.Function.Parameters.Property(
                    type="str", description="The question to ask."
                ),
            },
            required=["question"],
        ),
    ),
)


def oracle(question: str):
    return "oterm"
```

You need to install the package in the same environment where `oterm` is installed so that `oterm` can resolve it.

```bash
cd oracle
uv pip install . # or pip install .
```

#### Register the tool with oterm

You can register the tool with `oterm` by adding the tool definittion and callable to the `tools` section of the `oterm` configuration file. You can find the location of the configuration file's directory by running `oterm --data-dir`.

```json
{
    ...
    "tools": [{
        "tool": "oracle.tool:OracleTool",
        "callable": "oracle.tool:oracle"
    }]
}
```
Note the notation `module:object` for the tool and callable.

That's it! You can now use the tool in `oterm` with models that support it.

### Built-in example tools

The following example tools are currently built-in to `oterm`:

* `think` - provides the model with a way to think about a question before answering it. This is useful for complex questions that require reasoning. Use it for adding a "thinking" step to the model's response.
* `date_time` - provides the current date and time in ISO format.
* `shell` - allows you to run shell commands and use the output as input to the model. Obviously this can be dangerous, so use with caution.

These tools are defined in `src/oterm/tools`. You can make those tools available and enable them for selection when creating or editing a chat, by adding them to the `tools` section of the `oterm` configuration file. You can find the location of the configuration file's directory by running `oterm --data-dir`. So for example to enable the `shell` tool, you would add the following to the configuration file:

```json
{
    ...
    "tools": [{
        "tool": "oterm.tools.think:ThinkTool",
        "callable": "oterm.tools.think:think"
    }]
}
```
