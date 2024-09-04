# oterm

the text-based terminal client for [Ollama](https://github.com/jmorganca/ollama).

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* multiple persistent chat sessions, stored together with system prompt & parameter customizations in sqlite.
* can use any of the models you have pulled in Ollama, or your own custom models.
* allows for easy customization of the model's system prompt and parameters.

## Installation

Using `brew` for MacOS:

```bash
brew tap ggozad/formulas
brew install ggozad/formulas/oterm
```

Using `yay` (or any AUR helper) for Arch Linux:

```bash
yay -S oterm
```

Using `pip`:

```bash
pip install oterm
```

## Using

In order to use `oterm` you will need to have the Ollama server running. By default it expects to find the Ollama API running on `http://127.0.0.1:11434`. If you are running Ollama inside docker or on a different host/port, use the `OLLAMA_HOST` environment variable to customize the host/port. Alternatively you can use `OLLAMA_URL` to specify the full http(s) url. Setting `OTERM_VERIFY_SSL` to `False` will disable SSL verification.

```bash
OLLAMA_URL=http://host:port/api
```

To start `oterm` simply run:

```bash
oterm
```

### Commands
By pressing <kbd>^ Ctrl</kbd>+<kbd>p</kbd> you can access the command palette from where you can perform most of the chat management. The following commands are available:

* `New chat` - create a new chat session
* `Edit chat parameters` - edit the current chat session (change system prompt, parameters or format)
* `Rename chat` - rename the current chat session
* `Export chat` - export the current chat session as markdown
* `Delete chat` - delete the current chat session  

### Keyboard shortcuts

The following keyboard shortcuts are supported:

* <kbd>^ Ctrl</kbd>+<kbd>t</kbd> - toggle between dark/light theme
* <kbd>^ Ctrl</kbd>+<kbd>q</kbd> - quit

* <kbd>^ Ctrl</kbd>+<kbd>l</kbd> - switch to multiline input mode
* <kbd>^ Ctrl</kbd>+<kbd>i</kbd> - select an image to include with the next message
* <kbd>↑</kbd>     - navigate through history of previous prompts

* <kbd>^ Ctrl</kbd>+<kbd>Tab</kbd> - open the next chat
* <kbd>^ Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Tab</kbd> - open the previous chat

In multiline mode, you can press <kbd>Enter</kbd> to send the message, or <kbd>Shift</kbd>+<kbd>Enter</kbd> to add a new line at the cursor.

While Ollama is inferring the next message, you can press <kbd>Esc</kbd> to cancel the inference.

Note that some of the shortcuts may not work in a certain context, for example pressing <kbd>↑</kbd> while the prompt is in multi-line mode.

### Copy / Paste

It is difficult to properly support copy/paste in terminal applications. You can copy blocks to your clipboard as such:

* clicking a message will copy it to the clipboard.
* clicking a code block will only copy the code block to the clipboard.

For most terminals there exists a key modifier you can use to click and drag to manually select text. For example:
* `iTerm`  <kbd>Option</kbd> key.
* `Gnome Terminal` <kbd>Shift</kbd> key.
* `Windows Terminal` <kbd>Shift</kbd> key.


### Customizing models

When creating a new chat, you may not only select the model, but also customize the the `system` instruction as well as the `parameters` (such as context length, seed, temperature etc) passed to the model. For a list of all supported parameters refer to the [Ollama documentation](https://github.com/ollama/ollama/blob/main/docs/modelfile.md#valid-parameters-and-values). Checking the `JSON output` checkbox will force the model to reply in JSON format. Please note that `oterm` will not (yet) pull models for you, use `ollama` to do that. All the models you have pulled or created will be available to `oterm`.

You can also "edit" the chat to change the system prompt, parameters or format. Note, that the model cannot be changed once the chat has started.

### Chat session storage

All your chat sessions are stored locally in a sqlite database. You can customize the directory where the database is stored by setting the `OTERM_DATA_DIR` environment variable.

You can find the location of the database by running `oterm --db`.

### Screenshots

![Chat](screenshots/chat.png)
![Model selection](./screenshots/model_selection.png)
![Image selection](./screenshots/image_selection.png)

## License

This project is licensed under the [MIT License](LICENSE).
