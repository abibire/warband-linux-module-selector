#!/usr/bin/env python3
"""
Warband Module Picker
---------------------
Replacement for the broken mbw_config_linux tool. Lists the modules installed
under <game>/Modules and writes the chosen one to ~/.mbwarband/last_module_warband,
which is what the Linux/Mac build of Mount & Blade: Warband reads on startup.

Requires only Python 3 + Tkinter.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    sys.stderr.write(
        "Tkinter is missing. Install it with one of:\n"
        "  Debian/Ubuntu : sudo apt install python3-tk\n"
        "  Arch          : sudo pacman -S tk\n"
        "  Fedora        : sudo dnf install python3-tkinter\n"
    )
    sys.exit(1)

CONFIG_DIR = Path.home() / ".mbwarband"
CONFIG_FILE = CONFIG_DIR / "last_module_warband"
STEAM_APPID = "48700"
GAME_DIR_NAMES = ("MountBlade Warband", "Mount and Blade Warband", "Mount & Blade Warband")


# --------------------------------------------------------------------------- #
# Locating the game
# --------------------------------------------------------------------------- #

def steam_roots():
    """Candidate Steam installation roots, including Flatpak and Snap."""
    home = Path.home()
    return [
        home / ".steam/steam",
        home / ".steam/root",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        home / "snap/steam/common/.local/share/Steam",
    ]


def steam_library_paths():
    """Every steamapps/common directory Steam knows about."""
    found = []
    for root in steam_roots():
        common = root / "steamapps/common"
        if common.is_dir():
            found.append(common)

        vdf = root / "steamapps/libraryfolders.vdf"
        if vdf.is_file():
            try:
                text = vdf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            # Matches both the old flat format and the newer nested one.
            for path in re.findall(r'"path"\s*"([^"]+)"', text):
                extra = Path(path) / "steamapps/common"
                if extra.is_dir():
                    found.append(extra)

    # De-duplicate, preserving order.
    seen, unique = set(), []
    for path in found:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def find_game_dir():
    """Best guess at the directory containing Modules/."""
    candidates = []

    for library in steam_library_paths():
        for name in GAME_DIR_NAMES:
            candidates.append(library / name)

    home = Path.home()
    for base in (home / "GOG Games", home / "Games", home):
        for name in GAME_DIR_NAMES:
            candidates.append(base / name)
            candidates.append(base / name / "game")   # GOG layout

    for candidate in candidates:
        if (candidate / "Modules").is_dir():
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Modules and config
# --------------------------------------------------------------------------- #

def list_modules(game_dir):
    """Directory names under Modules/ that contain a module.ini."""
    modules_dir = Path(game_dir) / "Modules"
    if not modules_dir.is_dir():
        return []
    names = [
        entry.name
        for entry in modules_dir.iterdir()
        if entry.is_dir() and (entry / "module.ini").is_file()
    ]
    # Native first, then alphabetical, case-insensitively.
    return sorted(names, key=lambda n: (n != "Native", n.lower()))


def read_current_module():
    try:
        return CONFIG_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def write_module(name):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # No trailing newline: the engine's parser is fussy about the raw string.
    CONFIG_FILE.write_text(name, encoding="utf-8")


def launch_game(game_dir):
    """Prefer the Steam URL handler; fall back to the bundled shell script."""
    game_dir = Path(game_dir)
    if "steamapps" in game_dir.parts and shutil.which("steam"):
        subprocess.Popen(
            ["steam", f"steam://rungameid/{STEAM_APPID}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    for script in ("mb_warband.sh", "start.sh", "mb_warband_linux"):
        target = game_dir / script
        if target.is_file() and os.access(target, os.X_OK):
            subprocess.Popen(
                [str(target)],
                cwd=str(game_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
    return False


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #

class ModulePicker(ttk.Frame):
    def __init__(self, master, game_dir):
        super().__init__(master, padding=12)
        self.game_dir = game_dir
        self.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Select a module:").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        list_frame = ttk.Frame(self)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            list_frame, exportselection=False, activestyle="dotbox", height=10
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.listbox.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<Double-Button-1>", lambda _event: self.save())

        self.path_label = ttk.Label(self, foreground="#666", wraplength=420)
        self.path_label.grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.status = ttk.Label(self, wraplength=420)
        self.status.grid(row=3, column=0, sticky="w", pady=(4, 8))

        buttons = ttk.Frame(self)
        buttons.grid(row=4, column=0, sticky="ew")
        buttons.columnconfigure(1, weight=1)
        ttk.Button(buttons, text="Change folder\u2026", command=self.browse).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(buttons, text="Save & Play", command=self.save_and_play).grid(
            row=0, column=2, padx=(0, 6)
        )
        ttk.Button(buttons, text="Save", command=self.save).grid(row=0, column=3)

        self.refresh()

    # -- helpers ---------------------------------------------------------- #

    def refresh(self):
        self.listbox.delete(0, tk.END)

        if not self.game_dir:
            self.path_label.config(text="Game folder: not found")
            self.status.config(
                text="Couldn't locate Warband. Use \u201cChange folder\u2026\u201d "
                "to point at the directory containing Modules/."
            )
            return

        self.path_label.config(text=f"Game folder: {self.game_dir}")
        modules = list_modules(self.game_dir)

        if not modules:
            self.status.config(text="No modules found in that folder.")
            return

        for name in modules:
            self.listbox.insert(tk.END, name)

        current = read_current_module()
        index = modules.index(current) if current in modules else 0
        self.listbox.selection_set(index)
        self.listbox.see(index)

        if current in modules:
            self.status.config(text=f"Currently set to: {current}")
        elif current:
            self.status.config(
                text=f"Config names \u201c{current}\u201d, which isn't installed."
            )
        else:
            self.status.config(text="No module set yet; the game defaults to Native.")

    def selected_module(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Nothing selected", "Pick a module from the list first.")
            return None
        return self.listbox.get(selection[0])

    # -- actions ---------------------------------------------------------- #

    def browse(self):
        chosen = filedialog.askdirectory(title="Select your Warband folder")
        if not chosen:
            return
        chosen = Path(chosen)
        # Be forgiving if the user picks Modules/ itself.
        if chosen.name == "Modules" and chosen.is_dir():
            chosen = chosen.parent
        if not (chosen / "Modules").is_dir():
            messagebox.showerror(
                "Wrong folder", "That folder has no Modules/ subdirectory."
            )
            return
        self.game_dir = chosen
        self.refresh()

    def save(self):
        name = self.selected_module()
        if not name:
            return False
        try:
            write_module(name)
        except OSError as error:
            messagebox.showerror("Could not save", str(error))
            return False
        self.status.config(text=f"Saved. Warband will start in: {name}")
        return True

    def save_and_play(self):
        if not self.save():
            return
        if not launch_game(self.game_dir):
            messagebox.showwarning(
                "Saved, but couldn't launch",
                "The module is set. Start Warband the way you normally do.",
            )


def main():
    root = tk.Tk()
    root.title("Warband Module Picker")
    root.minsize(440, 360)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    game_dir = None
    if len(sys.argv) > 1:
        supplied = Path(sys.argv[1]).expanduser()
        game_dir = supplied if (supplied / "Modules").is_dir() else None
    if game_dir is None:
        game_dir = find_game_dir()

    ModulePicker(root, game_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
