# oterm
the text-based terminal client for [Ollama](https://github.com/jmorganca/ollama).

## Features

* intuitive and simple terminal UI, no need to run servers, frontends, just type `oterm` in your terminal.
* multiple persistent chat sessions, stored together with the context embeddings in sqlite.
* can use any of the models you have pulled in Ollama, or your own custom models.

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

### Screenshots
![Chat](screenshots/chat.png)
![Model selection](./screenshots/model_selection.png)

## License

This project is licensed under the [MIT License](LICENSE).
