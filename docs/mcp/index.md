# Model Context Protocol

`oterm` has support for Anthropic's open-source [Model Context Protocol](https://modelcontextprotocol.io). It connects to [MCP servers](https://github.com/modelcontextprotocol/servers) and exposes their tools to whichever model you're chatting with.

Add MCP servers under the `mcpServers` key in `oterm`'s [config.json](../app_config.md). The schema matches the convention used by Claude Desktop, Cursor, and pydantic-ai — so you can copy a config block between hosts.

!!! warning "Breaking changes from earlier oterm releases"
    The MCP integration was rewritten on top of pydantic-ai's MCP support. If you're upgrading, your existing `mcpServers` config likely needs the following edits:

    - **`auth: { type: bearer, token: "X" }`** is no longer recognised. Use `headers: { "Authorization": "Bearer X" }` instead. Old configs are silently dropped — you'll see 401s from the server until you migrate.
    - **`cwd`** is no longer recognised. Use an absolute path in `command` (or pass the working directory via `args`).
    - **`ws://` / `wss://` transports** are no longer supported. Use HTTP transport instead.
    - **MCP prompts** are gone — the "Use MCP prompt" command, the modal, and the prompt config in test fixtures are all removed.
    - **Stdio subprocess env is no longer inherited from the parent shell.** Declare every env var you need explicitly under `env`. Use `${VAR}` substitution to pull values from the parent environment without committing secrets — see [Environment variables](#environment-variables) below.

### Tools

[MCP tools](https://modelcontextprotocol.io/docs/concepts/tools) appear in oterm's tool selector and can be enabled per chat.

!!! note
    Not all models support tools. For models that don't, the tool selection is disabled.

    Smaller LLMs are often less capable with tools than larger ones. If you have issues, try reducing the number of tools attached to a chat, increasing the context size, or using a larger LLM.

### Transports

#### `stdio` transport

For local MCP servers. Accepts `command`, `args`, and `env`. For the [git](https://github.com/modelcontextprotocol/servers/tree/main/src/git) MCP server:

```json
{
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

For remote MCP servers over HTTP. The `url` must start with `http://` or `https://`. URLs ending in `/sse` are treated as SSE; everything else is streamable HTTP.

```json
{
  "mcpServers": {
    "my_mcp": {
      "url": "http://remote:port/path"
    }
  }
}
```

### HTTP headers (auth)

Use the `headers` dict to attach arbitrary HTTP headers — including `Authorization` for bearer-token auth:

```json
{
  "mcpServers": {
    "my_mcp": {
      "url": "http://remote:port/path",
      "headers": {
        "Authorization": "Bearer XXX"
      }
    }
  }
}
```

### Environment variables

For security, `stdio` MCP subprocesses do **not** inherit `oterm`'s parent environment. That keeps credentials like `OPENAI_API_KEY` or `AWS_SECRET_ACCESS_KEY` out of third-party MCP server processes unless you explicitly share them.

Declare env vars in the `env` dict of each server. Any string value (in `env`, `command`, `args`, `url`, or `headers`) can reference the parent environment via `${VAR}` (required) or `${VAR:-default}` (optional with fallback):

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
