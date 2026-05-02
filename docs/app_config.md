## Configuration

`oterm` is configured through a JSON file (`config.json`) and a small set of environment variables.

### Where `config.json` lives

The file is stored in a directory specific to your operating system. By default:

* Linux: `~/.local/share/oterm`
* macOS: `~/Library/Application Support/oterm`
* Windows: `C:/Users/<USER>/AppData/Roaming/oterm`

On Linux & MacOS we honour the `XDG_DATA_HOME` environment variable; the directory becomes `${XDG_DATA_HOME}/oterm`. Override the location entirely by setting `OTERM_DATA_DIR`.

If in doubt, run `oterm --data-dir` (or `uvx oterm --data-dir`) to print the resolved location.

### `config.json` at a glance

A complete example showing every supported key:

```json
{
  "splash-screen": true,
  "theme": "textual-dark",
  "keymap": {
    "next.chat": "ctrl+tab",
    "prev.chat": "ctrl+shift+tab",
    "new.chat": "ctrl+n",
    "show.logs": "ctrl+l",
    "quit": "ctrl+q",
    "newline": "shift+enter",
    "add.image": "ctrl+i"
  },
  "openaiCompatible": {
    "vllm": {
      "base_url": "http://localhost:8000/v1"
    },
    "openrouter": {
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "${OPENROUTER_API_KEY}"
    }
  },
  "mcpServers": {
    "everything": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"]
    }
  }
}
```

Each key is optional; the sections below cover them in turn. For `mcpServers`, see the full reference in [Model Context Protocol](mcp/index.md).

### `splash-screen` and `theme`

- `splash-screen` (boolean, default `true`) — whether the splash screen plays on startup.
- `theme` (string, default `"textual-dark"`) — the active theme. `oterm` rewrites this whenever you switch themes from the command palette, so you generally don't need to set it by hand.

### `keymap` — customizing key bindings

Sane defaults are provided, but terminal emulators and shells will sometimes intercept them. Override any of the bindings below by setting the matching key in the `keymap` block:

| ID          | Default            | Action                                                                  |
| ----------- | ------------------ | ----------------------------------------------------------------------- |
| `next.chat` | `ctrl+tab`         | Switch to the next chat tab.                                            |
| `prev.chat` | `ctrl+shift+tab`   | Switch to the previous chat tab.                                        |
| `new.chat`  | `ctrl+n`           | Open the new-chat dialog.                                               |
| `show.logs` | `ctrl+l`           | Open the log viewer.                                                    |
| `quit`      | `ctrl+q`           | Quit `oterm`.                                                           |
| `newline`   | `shift+enter`      | Insert a newline in the prompt. `ctrl+m` is also accepted as a fallback for terminals that can't distinguish `shift+enter` from `enter`, and is not configurable. |
| `add.image` | `ctrl+i`           | Attach an image to the next message.                                    |

### `openaiCompatible` — custom OpenAI-compatible endpoints

Connect to any OpenAI API-compatible service — local runners (vLLM, LM Studio, llama.cpp) or hosted aggregators (OpenRouter, LiteLLM) — by adding named endpoints under `openaiCompatible`:

```json
{
  "openaiCompatible": {
    "vllm": {
      "base_url": "http://localhost:8000/v1"
    },
    "openrouter": {
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "${OPENROUTER_API_KEY}"
    }
  }
}
```

Each entry takes:

- `base_url` (required) — the OpenAI-compatible API base URL.
- `api_key` (optional) — an API key. Reference an environment variable with `${VAR}` (or `${VAR:-default}` to fall back when unset), or pass a literal string. Omit for local endpoints that don't require authentication.

When configured, an **OpenAI Compatible** provider appears in the provider dropdown. Select it, choose your endpoint, and type the model name. If the endpoint exposes `/v1/models`, suggestions appear as you type.

## Providers and API keys

`oterm` discovers providers from your environment at startup. A provider appears in the new-chat dropdown only when its required environment variables are set. `.env` files in the working directory are loaded automatically.

| Provider          | Provider ID       | Required env var(s)                             |
| ----------------- | ----------------- | ----------------------------------------------- |
| Ollama            | `ollama`          | none — uses `OLLAMA_HOST` / `OLLAMA_URL`        |
| OpenAI            | `openai`          | `OPENAI_API_KEY`                                |
| OpenAI Responses  | `openai-responses`| `OPENAI_API_KEY`                                |
| Anthropic         | `anthropic`       | `ANTHROPIC_API_KEY`                             |
| Google AI         | `google-gla`      | `GOOGLE_API_KEY`                                |
| Google Vertex AI  | `google-vertex`   | `GOOGLE_APPLICATION_CREDENTIALS`                |
| Groq              | `groq`            | `GROQ_API_KEY`                                  |
| Mistral           | `mistral`         | `MISTRAL_API_KEY`                               |
| Cohere            | `cohere`          | `COHERE_API_KEY`                                |
| AWS Bedrock       | `bedrock`         | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`    |
| DeepSeek          | `deepseek`        | `DEEPSEEK_API_KEY`                              |
| Grok              | `grok`            | `GROK_API_KEY`                                  |
| Cerebras          | `cerebras`        | `CEREBRAS_API_KEY`                              |
| Hugging Face      | `huggingface`     | `HF_TOKEN`                                      |

The `openai-responses` provider routes through OpenAI's Responses API and enables image generation as a builtin tool — pick a Responses-compatible model (e.g. `gpt-5.4`) and ask for an image in the prompt. Returned images render inline in the chat; click one to save it to `$OTERM_DATA_DIR/downloads/`.

For any other backend with an OpenAI-compatible API, see the [`openaiCompatible`](#openaicompatible-custom-openai-compatible-endpoints) config block above.

## Environment variables

| Variable             | Default              | Purpose                                                                 |
| -------------------- | -------------------- | ----------------------------------------------------------------------- |
| `OTERM_DATA_DIR`     | OS-specific (above)  | Directory for `config.json` and `store.db`.                             |
| `OTERM_VERIFY_SSL`   | `True`               | Set to `False` to disable SSL verification when talking to Ollama.      |
| `OLLAMA_HOST`        | `127.0.0.1:11434`    | Ollama host/port. Used to derive `OLLAMA_URL` when it isn't set.        |
| `OLLAMA_URL`         | from `OLLAMA_HOST`   | Full Ollama base URL (e.g. `https://ollama.example.com`).               |

Provider-specific API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) are listed in the [provider table](#providers-and-api-keys) above.

## Chat storage

All chat sessions are stored locally in a sqlite database under `OTERM_DATA_DIR`. Run `oterm --db` to print its path.
