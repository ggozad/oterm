# oterm

the text-based terminal client for [Ollama](https://github.com/ollama/ollama).

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
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
* In-app log viewer for debugging and troubleshooting.
* Support sixel graphics for displaying images in the terminal.
* Support for Model Context Protocol (MCP) tools & prompts!
* Create custom commands that can be run from the terminal using oterm. Each of these commands is a chat, customized to your liking and connected to the tools of your choice.

### Screenshots
![Splash](https://raw.githubusercontent.com/ggozad/oterm/refs/heads/main/docs/img/splash.gif)
The splash screen animation that greets users when they start oterm.

![Chat](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/chat.png)
A view of the chat interface, showcasing the conversation between the user and the model.

![Model selection](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/customizations.svg)
The model selection screen, allowing users to choose and customize available models.

![Tool support](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/mcp_tools.svg)
oterm using the `git` MCP server to access its own repo.

![Image selection](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/image_selection.png)
The image selection interface, demonstrating how users can include images in their conversations.

![Theme](https://raw.githubusercontent.com/ggozad/oterm/main/docs/img/theme.svg)
oterm supports multiple themes, allowing users to customize the appearance of the interface.

## License

This project is licensed under the [MIT License](LICENSE).
