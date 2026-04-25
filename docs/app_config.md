### App configuration

The app configuration is stored as JSON in `config.json` in a directory specific to your operating system. By default:

* Linux: `~/.local/share/oterm`
* macOS: `~/Library/Application Support/oterm`
* Windows: `C:/Users/<USER>/AppData/Roaming/oterm`

On Linux & MacOS we honour the `XDG_DATA_HOME` environment variable. In that case, he directory will be `${XDG_DATA_HOME}/oterm`.

If in doubt you can get the directory where `config.json` can be found by running `oterm --data-dir` or `uvx oterm --data-dir` if you installed oterm using uvx.

You can set the following options in the configuration file:
```json
{ "splash-screen": true }
```

`splash-screen` controls whether the splash screen is shown on startup.

### Key bindings

We strive to have sane default key bindings, but there will always be cases where your terminal emulator or shell will interfere. You can customize select keybindings by editing the app config `config.json` file. The following are the defaults:

```json
{
  ...
  "keymap": {
    "next.chat": "ctrl+tab",
    "prev.chat": "ctrl+shift+tab",
    "quit": "ctrl+q",
    "newline": "shift+enter"
  }
}
```

### Providers / API keys

`oterm` discovers providers from your environment at startup. A provider appears in the new-chat dropdown only when its required environment variables are set. `.env` files in the working directory are loaded automatically.

| Provider          | Provider ID       | Required env var(s)                             |
| ----------------- | ----------------- | ----------------------------------------------- |
| Ollama            | `ollama`          | none — uses `OLLAMA_HOST` / `OLLAMA_URL`        |
| OpenAI            | `openai`          | `OPENAI_API_KEY`                                |
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

For any other backend with an OpenAI-compatible API — local runners like vLLM, LM Studio, or llama.cpp, or hosted aggregators like OpenRouter or LiteLLM — see [OpenAI-compatible providers](#openai-compatible-providers) below.

#### Ollama-specific environment variables

| Variable            | Default            | Purpose                                                                 |
| ------------------- | ------------------ | ----------------------------------------------------------------------- |
| `OLLAMA_HOST`       | `127.0.0.1:11434`  | Ollama host/port. Used to derive `OLLAMA_URL` if it is not set.         |
| `OLLAMA_URL`        | from `OLLAMA_HOST` | Full Ollama base URL (e.g. `https://ollama.example.com`).               |
| `OTERM_VERIFY_SSL`  | `True`             | Set to `False` to disable SSL verification when talking to Ollama.      |

### OpenAI-compatible providers

You can connect to any OpenAI API-compatible service (vLLM, OpenRouter, LiteLLM, etc.) by adding endpoints to the `openaiCompatible` section of your config:

```json
{
  ...
  "openaiCompatible": {
    "vllm": {
      "base_url": "http://localhost:8000/v1"
    },
    "openrouter": {
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "$OPENROUTER_API_KEY"
    }
  }
}
```

Each entry defines a named endpoint:

- `base_url` (required): The OpenAI-compatible API base URL.
- `api_key` (optional): An API key. Use `$ENV_VAR` syntax to reference an environment variable, or provide a literal string. Omit for local endpoints that don't require authentication.

When configured, an **OpenAI Compatible** provider appears in the provider dropdown. Select it, choose your endpoint, and type the model name. If the endpoint supports the `/v1/models` listing, model suggestions will appear as you type.

### Chat storage

All your chat sessions are stored locally in a sqlite database. You can customize the directory where the database is stored by setting the `OTERM_DATA_DIR` environment variable.

You can find the location of the database by running `oterm --db`.
