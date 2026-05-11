# oterm

[![Tests](https://github.com/ggozad/oterm/actions/workflows/test.yml/badge.svg)](https://github.com/ggozad/oterm/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/ggozad/oterm/graph/badge.svg)](https://codecov.io/gh/ggozad/oterm)

The terminal client for [Ollama](https://github.com/ollama/ollama), OpenAI, Anthropic, and any [pydantic-ai](https://ai.pydantic.dev/)-supported provider.

![Splash](https://raw.githubusercontent.com/ggozad/oterm/refs/heads/main/docs/img/splash.gif)

## Install

```bash
uvx oterm
```

Full install methods, configuration, and usage: **[oterm Documentation](https://ggozad.github.io/oterm/)**.

## What's new

* **Multi-provider, via pydantic-ai (breaking).** `oterm` is no longer Ollama-only — it drives any [pydantic-ai](https://ai.pydantic.dev/)-supported provider: OpenAI, Anthropic, Google (AI / Vertex), Groq, Mistral, Cohere, AWS Bedrock, DeepSeek, Cerebras, Grok, Hugging Face, OpenAI-compatible endpoints (vLLM, LM Studio, llama.cpp, OpenRouter, LiteLLM, …), and Ollama. Set the matching API key and the provider appears in the new-chat dropdown.
* **Refreshed chat UI.** Borderless accent-driven layout, auto-growing prompt, inline `[Image #N]` attachment tokens, a collapsing thinking section, and a live token-usage footer in place of the spinner.
* **Faster streaming.** Markdown is now updated as deltas arrive instead of being re-rendered on every token, so long responses don't slow the terminal as they grow.
* **MCP rewrite (breaking).** The `mcpServers` config block adopts pydantic-ai's standard schema (compatible with Claude Desktop / Cursor). See [docs/mcp](https://ggozad.github.io/oterm/mcp/) for the full migration notes.

## License

[MIT License](LICENSE).
