# Tools

`oterm` supports integration with tools. Tools are special "functions" that can provide external information to the LLM model that it does not otherwise have access to.

The following example tools are currently built-in to `oterm`:

* `fetch_url` - allows your models access to the web, fetches a URL and provides the content as input to the model.
* `date_time` - provides the current date and time in ISO format.
* `current_location` - provides the current location of the user (longitude, latitude, city, region, country). Uses [ipinfo.io](https://ipinfo.io) to determine the location.
* `current_weather` - provides the current weather in the user's location. Uses [OpenWeatherMap](https://openweathermap.org) to determine the weather. You need to provide your (free) API key in the OPEN_WEATHER_MAP_API_KEY environment variable.
* `shell` - allows you to run shell commands and use the output as input to the model. Obviously this can be dangerous, so use with caution.

These tools are defined in `src/oterm/tools`. You can make those tools available and enable them for selection when creating or editing a chat, by adding them to the `tools` section of the `oterm` configuration file. You can find the location of the configuration file's directory by running `oterm --data-dir`. So for example to enable the `shell` tool, you would add the following to the configuration file:

```json
{
    ...
    "tools": [{
        "tool": "oterm.tools.shell:ShellTool",
        "callable": "oterm.tools.shell:shell_command"
    }]
}
```

The above tools are meant as examples. To add your own tools, see the [tools documentation](docs/custom_tools.md).

### Model Context Protocol support

`oterm` has preliminary support for Anthropic's open-source [Model Context Protocol](https://modelcontextprotocol.io). While Ollama does not yet directly support the protocol, `oterm` attempts to bridge [MCP servers](https://github.com/modelcontextprotocol/servers) with Ollama by transforming MCP tools into Ollama tools.

To add an MCP server to `oterm`, simply add the server shim to oterm's `config.json`. For example for the [git](https://github.com/modelcontextprotocol/servers/tree/main/src/git) MCP server you would add something like the following to the `mcpServers` section of the `oterm` configuration file:

```json
{
  ...
  "mcpServers": {
    "git": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--mount",
        "type=bind,src=/Users/ggozad/dev/open-source/oterm,dst=/oterm",
        "mcp/git"
      ]
    }
  }
}
```

