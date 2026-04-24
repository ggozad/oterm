# Model Context Protocol

`oterm` has support for Anthropic's open-source [Model Context Protocol](https://modelcontextprotocol.io). While Ollama does not yet directly support the protocol, `oterm` attempts to bridge [MCP servers](https://github.com/modelcontextprotocol/servers) with Ollama.

To add an MCP server to `oterm`, simply add the server shim to oterm's [config.json](../app_config.md). The following MCP transports are supported

### Supported MCP Features
#### Tools
By transforming [MCP tools](https://modelcontextprotocol.io/docs/concepts/tools) into Ollama tools `oterm` provides full support.

!!! note
    Not all models are equipped to support tools. For those models that do not, the tool selection will be disabled.

    A lot of the smaller LLMs are not as capable with tools as larger ones you might be used to. If you experience issues with tools, try reducing the number of tools you attach to a chat, increase the context size, or use a larger LLM.


![Tool support](../img/mcp_tools.svg)
oterm using the `git` MCP server to access its own repo.

#### Sampling
`oterm` supports [MCP sampling](https://modelcontextprotocol.io/docs/concepts/sampling), acting as a geteway between Ollama and the servers it connects to. This way, an MCP server can request `oterm` to run a *completion* and even declare its model preferences and parameters!

### Transports
#### `stdio` transport

Used for running local MCP servers, the configuration supports the `command`, `args`, `env` & `cwd` parameters. For example for the [git](https://github.com/modelcontextprotocol/servers/tree/main/src/git) MCP server you would add something like the following to the `mcpServers` section of the `oterm` [configuration file](../app_config.md):

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
#### `Streamable HTTP` transport

Typically used to connect to remote MCP servers through Streamable HTTP, the only accepted parameter is the `url` parameter (should start with `http://` or `https://`). For example,

```json
{
  ...
  "mcpServers": {
    "my_mcp": {
			"url": "http://remote:port/path"
		}
  }
}
```

### Authentication
#### HTTP bearer authentication

`oterm` supports HTTP bearer authentication by use of tokens. Use
```json
{
  ...
  "mcpServers": {
    "my_mcp": {
			"url": "http://remote:port/path",
      "auth": {
        "type": "bearer",
        "token": "XXX"
      }
    }
  }
}
```

### Environment variables

For security, `stdio` MCP subprocesses do **not** inherit `oterm`'s parent environment. That keeps credentials like `OPENAI_API_KEY` or `AWS_SECRET_ACCESS_KEY` out of third-party MCP server processes unless you explicitly share them.

Declare env vars in the `env` dict of each server. Any string value (in `env`, `command`, `args`, `url`, or a bearer `token`) can reference the parent environment via `${VAR}` (required) or `${VAR:-default}` (optional with fallback):

```json
{
  "mcpServers": {
    "github": {
      "command": "${HOME}/.local/bin/mcp-github",
      "args": ["--repo", "${REPO:-ggozad/oterm}"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

If a referenced variable is not set and has no default, server setup fails with an error naming the missing variable.
