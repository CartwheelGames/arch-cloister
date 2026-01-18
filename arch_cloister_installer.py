#!/usr/bin/env python3
"""Cloister — automated Linux setup for arcade machines."""

import subprocess
from pathlib import Path
import shutil
import archinstall

# Constants ====================================================================

GAME_DIR = Path("/opt") / "game"
REPO_DIR = Path("/tmp") / "repo"

# Utilities ====================================================================

def run_command(command: str, check: bool=True):
    """Run a shell command and handle errors."""
    try:
        return subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error output: {e.stderr}")
        raise

def main():
    """Main function"""
    try:
        # Ask for Game binary from local usb

        # Validate game binary

        # Copy game binary into /opt/game folder on target OS install

        print("Cloning the installer repo locally")
        run_command("pacman --noconfirm -S git")
        if REPO_DIR.exists():
            run_command(f"git -C {REPO_DIR} pull origin main")
        else:
            run_command(f"git clone https://www.github.com/CartwheelGames/arch-cloister {REPO_DIR}")

        print("Copying the custom archinstall script into the relevant directory")
        archinstall_scripts_dir = Path(archinstall.__file__).parent / "scripts"
        shutil.copyfile(REPO_DIR / "custom_script.py", archinstall_scripts_dir  / "custom_script.py")

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
    main()
