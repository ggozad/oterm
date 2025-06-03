# oterm

the terminal client for [Ollama](https://github.com/ollama/ollama).

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* supports Linux, MacOS, and Windows and most terminal emulators.
* multiple persistent chat sessions, stored together with system prompt & parameter customizations in sqlite.
* support for Model Context Protocol (MCP) tools & prompts integration.
* can use any of the models you have pulled in Ollama, or your own custom models.
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
* Support for "thinking" mode for models that support it.
* Support for streaming with tools!
* Messages UI styling improvements.
* MCP Sampling is here in addition to MCP tools & prompts! Also support for SSE & WebSocket transports for MCP servers.

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
