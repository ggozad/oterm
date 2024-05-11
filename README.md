### Adding RAG

#### Why?
I hate SEO. Usually, when trying to Google while developing I keep coming back to a couple of trusted sources of
documentation, while the top search results are usually short blog posts barely scratching the surface of my question.
I like Ollama, I like oterm and I wanted to test how it would be if I had local copies of the documentation which
get fed into a local LLM.

#### How?
Install from source, preferably through [pipx](https://github.com/pypa/pipx). Aside from the `oterm` command, 
it also exposes `rtfm-init`. This command takes in a directory and creates a database of text chunks and embeddings, which
can later be linked into your chat session.

To link it, press `CTRL+k` (keybind not shown in the footer due to space). This opens a screen where `+` adds a context source, 
while `-` removes it. `ESC` exits the screen and these directories are then stored.

When posting a query, top 3 chunks (by similarity) are fed alongside your query to the model.

#### Tinkering
I've tried to localize the changes and dependencies as much as possible. 
`oterm.embeddings` contains code to generate the DB and embeddings (just a `np.memmap`).
`oterm.app.widgets.knowledge` defines the extra screens to show when browsing for stores.
Rest of the differences with oterm source is just integration for these two modules with the rest.

[sentence-transformers](https://pypi.org/project/sentence-transformers/) is used to fetch the text embedding model,
[inscriptis](https://pypi.org/project/inscriptis/) is to provide support with web pages,
while [semantic-text-splitter](https://pypi.org/project/semantic-text-splitter/) is used for the chunking code.

Huge thanks to the developers and maintainers of these projects.

#### Final notes
Probably won't update the RAG changes much, only if the API of dependencies changes somewhat. Other than that,
I'll try to ensure that all the other changes in oterm are reflected in this fork.

# oterm

the text-based terminal client for [Ollama](https://github.com/jmorganca/ollama).

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* multiple persistent chat sessions, stored together with the context embeddings and system prompt customizations in sqlite.
* can use any of the models you have pulled in Ollama, or your own custom models.
* allows for easy customization of the model's system prompt and parameters.

## Installation

Using `brew` for MacOS:

```bash
brew tap ggozad/formulas
brew install ggozad/formulas/oterm
```

Using `pip`:

```bash
pip install oterm
```

## Using

In order to use `oterm` you will need to have the Ollama server running. By default it expects to find the Ollama API running on `http://0.0.0.0:11434`. If you are running Ollama inside docker or on a different host/port, use the `OLLAMA_HOST` environment variable to customize the host/port. Alternatively you can use `OLLAMA_URL` to specify the full http(s) url. Setting `OTERM_VERIFY_SSL` to `False` will disable SSL verification.

```bash
OLLAMA_URL=http://host:port/api
```

The following keyboard shortcuts are supported:

* <kbd>^ Ctrl</kbd>+<kbd>N</kbd> - create a new chat session
* <kbd>^ Ctrl</kbd>+<kbd>E</kbd> - edit the chat session (change template, system prompt or format)
* <kbd>^ Ctrl</kbd>+<kbd>R</kbd> - rename the current chat session
* <kbd>^ Ctrl</kbd>+<kbd>S</kbd> - export the current chat session as markdown
* <kbd>^ Ctrl</kbd>+<kbd>X</kbd> - delete the current chat session
* <kbd>^ Ctrl</kbd>+<kbd>T</kbd> - toggle between dark/light theme
* <kbd>^ Ctrl</kbd>+<kbd>Q</kbd> - quit

* <kbd>^ Ctrl</kbd>+<kbd>L</kbd> - switch to multiline input mode
* <kbd>^ Ctrl</kbd>+<kbd>P</kbd> - select an image to include with the next message
* <kbd>↑</kbd>     - navigate through history of previous prompts

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

When creating a new chat, you may not only select the model, but also customize the `template` as well as the `system` instruction to pass to the model. Checking the `JSON output` checkbox will cause the model reply in JSON format. Please note that `oterm` will not (yet) pull models for you, use `ollama` to do that. All the models you have pulled or created will be available to `oterm`.

You can also "edit" the chat to change the template, system prompt or format. Note, that the model cannot be changed once the chat has started. In addition whatever "context" the chat had (an embedding of the previous messages) will be kept.

### Chat session storage

All your chat sessions are stored locally in a sqlite database. You can customize the directory where the database is stored by setting the `OTERM_DATA_DIR` environment variable.

You can find the location of the database by running `oterm --db`.

### Screenshots

![Chat](screenshots/chat.png)
![Model selection](./screenshots/model_selection.png)
![Image selection](./screenshots/image_selection.png)

## License

This project is licensed under the [MIT License](LICENSE).
