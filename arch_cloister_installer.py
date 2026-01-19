#!/usr/bin/env python3
"""Cloister — automated Linux setup for arcade machines."""

import os
import sys
import subprocess
from pathlib import Path
import shutil
import curses
import archinstall

# Constants ====================================================================

GAME_DIR = Path("/opt") / "game"
REPO_DIR = Path("/tmp") / "repo"
REPO_URL = "https://www.github.com/CartwheelGames/arch-cloister"

# Utilities ====================================================================

def run_command(command: str, check: bool=True):
    """Run a shell command and handle errors."""
    try:
        return subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error output: {e.stderr}")
        raise

def find_game_bin(dir_path: Path) -> str:
    "Search the game binary in the game directory"
    print("Searching for the game binary. Do it here, walk the directory")
    for item in dir_path.iterdir():
        if item.is_file() and os.access(item, os.X_OK):
            return str(item.resolve())
    return ""

def validate_game_binary(game_bin: str):
    """Validate the game binary"""
    print(f"Validating the game binary {game_bin}")
    if not Path(game_bin).exists():
        print(f"Error: Game binary not found at {game_bin}")
        sys.exit(1)
    if not os.access(game_bin, os.X_OK):
        print(f"Error: Game binary is not executable at {game_bin}")
        sys.exit(1)

def show_game_directory_dialog(stdscr: curses.window) -> str:
    """Show a TUI dialog to select the game binary directory from USB."""
    # Placeholder for TUI dialog implementation
    curses.curs_set(0)  # hide cursor
    stdscr.clear()
    options = ["Local Game", "Remote Game"]
    current_selection = 0

    run_command("pacman -S --noconfirm fzf udiskie")

    def draw_menu():
        stdscr.clear()
        stdscr.addstr(1, 2, "Select game source:", curses.A_BOLD)
        for idx, option in enumerate(options):
            x = 4
            y = 3 + idx
            if idx == current_selection:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(y, x, option)
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(y, x, option)
        stdscr.refresh()

    while True:
        draw_menu()
        key = stdscr.getch()
        if key == curses.KEY_UP and current_selection > 0:
            current_selection -= 1
        elif key == curses.KEY_DOWN and current_selection < len(options) - 1:
            current_selection += 1
        elif key in [curses.KEY_ENTER, 10, 13]:
            break

    stdscr.clear()
    curses.curs_set(1)  # show cursor for input

    if current_selection == 0:
        stdscr.addstr(2, 2, "Enter local game path: ")
    else:
        stdscr.addstr(2, 2, "Enter remote game URL: ")

    stdscr.refresh()
    curses.echo()
    if current_selection == 0:
        input_str = run_command("fzf", check=False).stdout.strip()
    else:
        input_str = stdscr.getstr(2, 25, 60).decode("utf-8")
    curses.noecho()

    stdscr.clear()
    stdscr.addstr(4, 2, f"You selected: {options[current_selection]}")
    stdscr.addstr(5, 2, f"Input: {input_str}")
    stdscr.addstr(7, 2, "Press any key to exit...")
    stdscr.refresh()
    stdscr.getch()
    #uninstall fzf
    run_command("pacman -R --noconfirm fzf udiskie")

    return input_str

def main(stdscr: curses.window):
    """Main function"""
    try:
        # TUI Screen that asks for Game binary from local usb
        game_origin = show_game_directory_dialog(stdscr)
        game_file_path = Path(game_origin)
        # If remote archive, download it and extract to /tmp/game
        if game_origin.startswith("http://") or game_origin.startswith("https://"):
            print(f"Downloading game from remote URL: {game_origin}")
            archive_path = Path("/tmp") / "game_archive"
            run_command(f"mkdir -p {archive_path}")
            file_name = game_origin.split("/")[-1]
            game_file_path = archive_path / file_name
            run_command(f"curl -L {game_origin} -o {archive_path / file_name}")

        # Copy or extract game files to /etc/skel/game for archinstall to pick up
        # and include in new user home directories
        skel_game_path = Path("/etc") / "skel" / "game"
        is_archive = any(game_file_path.suffix in ext for ext in [".zip"])
        if is_archive:
            run_command("pacman --noconfirm -S unzip")
            print(f"Extracting game archive: {game_file_path}")
            run_command(f"mkdir -p {skel_game_path}")
            run_command(f"unzip {game_file_path} -d {skel_game_path}")
            run_command("pacman --noconfirm -R unzip")
        else:
            shutil.copytree(game_file_path, skel_game_path, dirs_exist_ok=True)
        # Validate game binary
        game_bin = find_game_bin(skel_game_path)
        validate_game_binary(game_bin)

        print("Cloning the installer repo locally")
        run_command("pacman --noconfirm -S git")
        if REPO_DIR.exists():
            run_command(f"git -C {REPO_DIR} pull origin main")
        else:
            run_command(f"git clone --depth 1 {REPO_URL} {REPO_DIR}")
        print("Copying the custom archinstall script into the relevant directory")
        archinstall_scripts_dir = Path(archinstall.__file__).parent / "scripts"
        shutil.copyfile(REPO_DIR / "custom_script.py",
                        archinstall_scripts_dir  / "custom_script.py")

        print("Running archinstall")
        subprocess.run(["sudo",
                        "archinstall",
                        "--script",
                        "custom_script",
                        "--dry-run",
                        "--config",
                        REPO_DIR / "install_config.json"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Cloister installer failed to install the operating system: {e}")

if __name__ == "__main__":
    curses.wrapper(main)
