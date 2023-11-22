# oterm
the text-based terminal client for [Ollama](https://github.com/jmorganca/ollama).

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* multiple persistent chat sessions, stored together with the context embeddings and template/system prompt customizations in sqlite.
* can use any of the models you have pulled in Ollama, or your own custom models.
* allows for easy customization of the model's template, system prompt and parameters.

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

In order to use `oterm` you will need to have the Ollama server running. By default it expects to find the Ollama API running on `http://localhost:11434/api`. If you are running Ollama inside docker or on a different host/port, use the `OLLAMA_URL` environment variable to customize the API url. Setting `OTERM_VERIFY_SSL` to `False` will disable SSL verification.

```bash
OLLAMA_URL=http://host:port/api
```

`oterm` will not (yet) pull models for you, please use `ollama` to do that. All the models you have pulled or created will be available to `oterm`.

### Customizing models

When creating a new chat, you may not only select the model, but also customize the `template` as well as the `system` instruction to pass to the model. Checking the `JSON output` checkbox will cause the model reply in JSON format.

### Screenshots
![Chat](screenshots/chat.png)
![Model selection](./screenshots/model_selection.png)

## License

This project is licensed under the [MIT License](LICENSE).
