# oterm

the terminal client for [Ollama](https://github.com/ollama/ollama), OpenAI, Anthropic, and any [pydantic-ai](https://ai.pydantic.dev/)-supported provider.

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* multiple persistent chat sessions, stored together with system prompt & parameter customizations in sqlite.
* talks to Ollama, OpenAI, Anthropic, Google (AI / Vertex), Groq, Mistral, Cohere, AWS Bedrock, DeepSeek, Cerebras, Grok, Hugging Face, and any OpenAI-compatible endpoint — local (vLLM, LM Studio, llama.cpp, …) or hosted (OpenRouter, LiteLLM, …).
* support for Model Context Protocol (MCP) tools and sampling.
* allows for easy customization of the model's system prompt and parameters.
* supports tools integration for providing external information to the model.

## Installation

See the [Installation](installation.md) section.

## Using oterm

`oterm` picks up providers automatically from your environment. If [Ollama](https://github.com/ollama/ollama) is running on `http://127.0.0.1:11434` it shows up out of the box; for any other hosted provider, set the relevant API key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) and it appears in the provider dropdown. For other local runners (vLLM, LM Studio, llama.cpp, …) or hosted OpenAI-compatible endpoints (OpenRouter, LiteLLM, …), add an entry to the `openaiCompatible` section of `config.json`. See [Providers / API keys](app_config.md#providers-api-keys) and [OpenAI-compatible providers](app_config.md#openai-compatible-providers).

If you are running Ollama inside docker or on a different host/port, use the `OLLAMA_HOST` environment variable to customize the host/port. Alternatively you can use `OLLAMA_URL` to specify the full http(s) url. Setting `OTERM_VERIFY_SSL` to `False` will disable SSL verification.

```bash
OLLAMA_URL=http://host:port
```

To start `oterm` simply run:

```bash
oterm
```

If you installed oterm using `uvx`, you can also start it using:

```bash
uvx oterm
```

### Screenshots
![Splash](img/splash.gif)
The splash screen animation that greets users when they start oterm.

![Chat](img/chat.png)
A view of the chat interface, showcasing the conversation between the user and the model.

![Theme](./img/theme.png)
oterm supports multiple themes, allowing users to customize the appearance of the interface.

## License

This project is licensed under the [MIT License](https://raw.githubusercontent.com/ggozad/oterm/main/LICENSE).
