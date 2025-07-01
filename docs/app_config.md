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

### Chat storage

All your chat sessions are stored locally in a sqlite database. You can customize the directory where the database is stored by setting the `OTERM_DATA_DIR` environment variable.

You can find the location of the database by running `oterm --db`.
