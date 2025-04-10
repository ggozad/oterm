### App configuration

The app configuration is stored in a directory specific to your operating system, by default:

* Linux: `~/.local/share/oterm/config.json`
* macOS: `~/Library/Application Support/oterm/config.json`
* Windows: `C:/Users/<USER>/AppData/Roaming/oterm/config.json`

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