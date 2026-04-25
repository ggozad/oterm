# oterm

the terminal client for [Ollama](https://github.com/ollama/ollama), OpenAI, Anthropic, and any [pydantic-ai](https://ai.pydantic.dev/)-supported provider.

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* supports Linux, MacOS, and Windows and most terminal emulators.
* multiple persistent chat sessions, stored together with system prompt & parameter customizations in sqlite.
* talks to Ollama, OpenAI, Anthropic, Google (AI / Vertex), Groq, Mistral, Cohere, AWS Bedrock, DeepSeek, Cerebras, Grok, Hugging Face, and any OpenAI-compatible endpoint — local (vLLM, LM Studio, llama.cpp, …) or hosted (OpenRouter, LiteLLM, …).
* support for Model Context Protocol (MCP) tools and sampling.
* allows for easy customization of the model's system prompt and parameters.
* supports tools integration for providing external information to the model.

## Quick install

```bash
uvx oterm
```
See [Installation](https://ggozad.github.io/oterm/installation) for more details.

## Documentation

[oterm Documentation](https://ggozad.github.io/oterm/)

## What's new
* **Breaking:** `oterm` now talks to LLMs via [pydantic-ai](https://ai.pydantic.dev/), unlocking first-class support for OpenAI, Anthropic, Groq, OpenAI-compatible endpoints, and more — alongside Ollama.
* **Breaking:** the MCP `mcpServers` config block adopts pydantic-ai's standard schema (compatible with Claude Desktop / Cursor). See migration notes in [docs/mcp](https://ggozad.github.io/oterm/mcp/).
* [Example](https://ggozad.github.io/oterm/rag_example) on how to do RAG with [haiku.rag](https://github.com/ggozad/haiku.rag).
* `oterm` is now part of Homebrew!
* Support for "thinking" mode for models that support it.
* Support for streaming with tools!
* Messages UI styling improvements.

### Screenshots
![Splash](https://raw.githubusercontent.com/ggozad/oterm/refs/heads/main/docs/img/splash.gif)
The splash screen animation that greets users when they start oterm.

![Chat](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/chat.png)
A view of the chat interface, showcasing the conversation between the user and the model.

![Model selection](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/customizations.png)
The model selection screen, allowing users to choose and customize available models.

![Tool support](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/mcp_tools.svg)
oterm using the `git` MCP server to access its own repo.

![Image selection](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/image_selection.png)
The image selection interface, demonstrating how users can include images in their conversations.

![Theme](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/theme.png)
oterm supports multiple themes, allowing users to customize the appearance of the interface.

## License

This project is licensed under the [MIT License](LICENSE).
