#!/usr/bin/env python3
"""Cloister — automated Linux setup for arcade machines."""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path
import pwd

# Constants ====================================================================

ARCADE_USER = "arcade"
DEST_PATH = Path("/opt") / "game"
SCREENSHOTS_PATH = Path("/opt") / "screenshots"

# Utilities ====================================================================

def run_command(command: str, check: bool=True):
    """Run a shell command and handle errors."""
    try:
        return subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error output: {e.stderr}")
        raise

def write_file(file_path: Path, content: str, mode: str="w", is_executable: bool=False):
    """Write content to a file with proper error handling.
    
    Args:
        filepath (str): Path to the file to write
        content (str): Content to write to the file
        mode (str): File opening mode ("w" for write, "a" for append)
    """
    try:
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)
        if is_executable:
            os.chmod(file_path, 0o755)
    except Exception as e:
        print(f"Error writing to file {file_path}: {e}")
        raise

def make_dir(dir_path: Path):
    """Creates a directory, idempotently"""
    Path(dir_path).mkdir(parents=True, exist_ok=True)

def user_exists(username: str):
    """Check if a user exists using the pwd module."""
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def parse_args():
    """Parse arguments"""
    print("Parsing arguments")
    # Create argument parser and add properties
    parser = argparse.ArgumentParser(description="Cloister Linux Setup")
    parser.add_argument("game_bin", help="Path to the game binary")
    parser.add_argument("--width", type=int, help="Screen width")
    parser.add_argument("--height", type=int, help="Screen height")
    parser.add_argument("--offline", action="store_true",
                        help="Skip updates, upgrades and package downloads")
    return parser.parse_args()

def validate_game_binary(game_bin: str):
    """Validate the game binary"""
    print(f"Validating the game binary {game_bin}")
    if not Path(game_bin).exists():
        print(f"Error: Game binary not found at {game_bin}")
        sys.exit(1)
    if not os.access(game_bin, os.X_OK):
        print(f"Error: Game binary is not executable at {game_bin}")
        sys.exit(1)

def detect_windows_binary(game_bin: str):
    """Detect if the binary is Windows or Linux"""
    is_windows_game = False
    try:
        result = run_command(f"file -bL '{game_bin}'", check=False)
        if "PE32" in result.stdout:
            print("The binary is a Windows executable")
            is_windows_game = True
        elif "ELF" in result.stdout:
            print("The binary is a Linux executable.")
        else:
            raise ValueError("The binary was not built for Linux or Windows")
    except subprocess.CalledProcessError as e:
        print(f"Error detecting binary type: {e}")
        sys.exit(1)
    return is_windows_game

def get_screen_resolution(width: int, height: int):
    """Get the screen resolution"""
    output = subprocess.check_output("xrandr").decode("utf-8")
    # Find the line with the current resolution (indicated by '*')
    for line in output.splitlines():
        if '*' in line:
            # The resolution is typically the first element (e.g., '1920x1080')
            resolution = line.split()[0]
            split = resolution.split('x')
            if width == 0:
                width = int(split[0])
            if height == 0:
                height = int(split[1])
    return width, height

def is_service_active(service_name: str):
    """Returns true if a service exists and is active"""
    try:
        result = run_command(f"systemctl is-active --quiet {service_name}", check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def disable_service(service_name: str):
    """Disables a systemd service"""
    if is_service_active(service_name):
        run_command(f"systemctl disable {service_name}")

def enable_service(service_name: str):
    """Enables a systemd service"""
    if not is_service_active(service_name):
        run_command(f"systemctl enable {service_name}")

# Business Logic ===============================================================

def copy_game_files(game_dir: Path):
    """Copy game files to the arcade user directory"""
    print(f"Copying over the game files to the {ARCADE_USER} user")
    shutil.rmtree(DEST_PATH, ignore_errors=True)
    make_dir(DEST_PATH)
    shutil.copytree(game_dir, DEST_PATH, dirs_exist_ok=True)
    run_command(f"chmod -R 777 {DEST_PATH}")

# Main Logic ===================================================================
