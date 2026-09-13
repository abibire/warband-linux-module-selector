# Warband Module Picker

A small GUI for choosing which module Mount & Blade: Warband loads on Linux.

The native Linux build has no launcher, and its config tool (`mbw_config_linux`)
fails on most modern distros because of missing 32-bit Qt4 and audio libraries.
This script replaces it: pick a module, hit Save, start the game.

## Requirements

Python 3 and Tkinter. Tkinter ships with Python but is usually a separate package:

| Distro         | Package           |
| -------------- | ----------------- |
| Debian/Ubuntu  | `python3-tk`      |
| Arch           | `tk`              |
| Fedora         | `python3-tkinter` |

## Usage

```sh
chmod +x warband-module-picker.py
./warband-module-picker.py
```

Optionally pass the game directory (the one containing `Modules/`) if
autodetection misses it:

```sh
./warband-module-picker.py ~/games/MountBlade\ Warband
```

## What it does

- Finds the game across Steam libraries, including Flatpak and Snap installs,
  by reading `libraryfolders.vdf`. GOG layouts are checked too.
- Lists every directory under `Modules/` that contains a `module.ini`.
- Writes your choice to `~/.mbwarband/last_module_warband`, which is the file
  the engine reads at startup.
- **Save & Play** also launches the game — via Steam if the install lives under
  `steamapps`, otherwise via `mb_warband.sh`.

Nothing in the game directory is modified.