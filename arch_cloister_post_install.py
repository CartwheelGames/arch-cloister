#!/usr/bin/env python3
"""Cloister — automated Linux setup for arcade machines."""

import os
import sys
import subprocess
import argparse
from pathlib import Path
import pwd

# Constants ====================================================================

ARCADE_USER = "arcade"
GAME_DIR = Path("/opt") / "game"
SCREENSHOTS_PATH = Path("/opt") / "screenshots"
TERMINAL_APP = "qterminal"

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

def get_game_bin():
    "Find the game binary in the game directory"
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

def get_screen_resolution():
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

def hide_bootloader():
    """Set the timeout of the bootloader to 0"""
    print("Hiding the bootloader menu")
    run_command("bootctl set-timeout 0")

def create_arcade_user():
    """Create dedicated arcade user account"""
    if not user_exists(ARCADE_USER):
        print(f"Adding the {ARCADE_USER} user")
        run_command(f"useradd -m -s /bin/bash {ARCADE_USER}")
        run_command(f"passwd -d {ARCADE_USER}")

def setup_autologin():
    """Setup automatic login for arcade user using greetd and disable competing desktop managers"""
    print(f"Setting up automatic login for the {ARCADE_USER} user")
    override_dir = Path("/etc") / "greetd"
    make_dir(override_dir)
    autologin_conf = override_dir / "config.toml"
    write_file(autologin_conf, f"""[terminal]
vt = "next"
[default_session]
command = "tuigreet --user-menu --cmd startx"
user = "greeter"
[initial_session]
user = "{ARCADE_USER}"
command = "startx"
""")
    disable_service("sddm.service")
    enable_service("greetd.service")

def setup_screenshots_directory():
    """Setup screenshots directory"""
    print("Setting up the screenshots directory")
    make_dir(SCREENSHOTS_PATH)
    run_command(f"chmod 777 {SCREENSHOTS_PATH}")

def set_desktop_environments(admin_user: str):
    """Ensure the correct desktop environment is loaded for each user"""
    admin_init_path = Path("/home") / admin_user / ".xinitrc"
    write_file(admin_init_path, """#!/bin/sh
exec startlxqt
""")
    arcade_init_path = Path("/home") / ARCADE_USER / ".xinitrc"
    write_file(arcade_init_path, """#!/bin/sh
exec openbox-session
""")
    run_command(f"chown {ARCADE_USER}:{ARCADE_USER} {arcade_init_path}")

def setup_wine_support(offline: bool):
    """Setup Wine compatibility layer for Windows games"""
    if offline:
        print("Offline mode: skipping Wine installation and setup")
        return
    print("Executable is a Windows app, preparing Wine")
    run_command("dpkg --add-architecture i386")
    wine_user_path = Path("/home") / ARCADE_USER / ".wine"
    make_dir(wine_user_path)
    run_command(f"sudo -u {ARCADE_USER}/ WINEPEFIX='{wine_user_path}' wineboot --init")

def setup_screen_resolution(width: int, height: int):
    """Setup screen resolution for arcade user"""
    print(f"Setting the screen resolution layout for the {ARCADE_USER} user")
    screenlayout_path = Path("/home") / ARCADE_USER / ".screenlayout"
    make_dir(screenlayout_path)
    # Get connected outputs
    try:
        command = "xrandr --query | grep -E \" connected| disconnected\" | cut -d\" \" -f1"
        result = run_command(command, check=False)
        outputs = result.stdout.strip().split("\n")
        outputs = [o for o in outputs if o]
    except subprocess.CalledProcessError:
        outputs = ["HDMI-1", "VGA-1", "eDP-1"]  # Default outputs
    xrandr_cmd = "xrandr"
    for output in outputs:
        xrandr_cmd += f" --output {output} --mode {width}x{height} --rate 60"
    resolution_script_path = Path(screenlayout_path) / "arcade_resolution.sh"
    write_file(resolution_script_path, f"""#!/bin/bash
{xrandr_cmd}
""", is_executable=True)

def setup_openbox_autostart(game_name: str,
                            is_windows_game: bool,
                            width: int,
                            height: int):
    """Setup Openbox autostart for arcade user"""
    print(f"Configuring the autostart file for the {ARCADE_USER} user")
    openbox_path = Path("/home") / ARCADE_USER / ".config" / "openbox"
    make_dir(openbox_path)
    run_game_command = f"\"{GAME_DIR}/{game_name}\""
    if is_windows_game:
        run_game_command = ("wine explorer /desktop=Arcade,"
                            f"{width}x{height} {run_game_command}")
    resolution_script_path = Path("/home") / ARCADE_USER / ".screenlayout" / "arcade_resolution.sh"
    autostart_path = Path(openbox_path) / "autostart"
    write_file(autostart_path, f"""# Disable DPMS
xset -dpms &
# Disable screensaver
xset s off &
# Disable screen blanking
xset s noblank &
# Apply the resolution
{resolution_script_path} &
# Hide the cursor
unclutter -idle 0.01 -root &
# Cache all fonts to prevent the system from hanging on initial font load
fc-cache -fv &
# Infinite loop with a check for termination
while true; do
    {run_game_command}
    sleep 1 &
done
""")

def setup_openbox_keybindings():
    """Setup keyboard shortcuts for arcade user.
    The resulting openbox configuration is extremely minimal
    """
    print("Configuring keybindings for the arcade user")
    openbox_path = Path("/home") / ARCADE_USER / ".config" / "openbox"
    make_dir(openbox_path)
    openbox_config_path = Path(openbox_path) / "rc.xml"
    write_file(openbox_config_path, f"""<?xml version="1.0" encoding="UTF-8"?>
<openbox_config>
  <focus>
    <focusNew>yes</focusNew>
  </focus>
  <keyboard>
    <keybind key="A-F4">
      <action name="Close"/>
    </keybind>
    <keybind key="C-A-Delete">
      <action name="Execute">
        <command>
            openbox --exit
        </command>
      </action>
    </keybind>
        <keybind key="A-F7">
            <action name="Execute">
                <command>{TERMINAL_APP}</command>
            </action>
        </keybind>
        <keybind key="A-F8">
            <action name="Execute">
                <command>{TERMINAL_APP} -e nmtui</command>
            </action>
        </keybind>
    <keybind key="A-F9">
      <action name="Execute">
        <command>{TERMINAL_APP} -e wiremix</command>
      </action>
    </keybind>
    <keybind key="A-F10">
      <action name="Execute">
        <command>arandr</command>
      </action>
    </keybind>
        <keybind key="A-F11">
            <action name="Execute">
                <command>{TERMINAL_APP} -e htop</command>
            </action>
        </keybind>
    <keybind key="A-F12">
      <action name="Execute">
        <command>scrot '{SCREENSHOTS_PATH}/%Y-%m-%d-%H%M%S.png'</command>
      </action>
    </keybind>
  </keyboard>
  <applications>
        <application name="{TERMINAL_APP}">
            <maximized>yes</maximized>
        </application>
  </applications>
</openbox_config>
""")

def ensure_arcade_user_owns_home():
    """Ensure the arcade user owns their home directory"""
    run_command(f"chown -R {ARCADE_USER}:{ARCADE_USER} /home/{ARCADE_USER}")

# Main Logic ===================================================================

def main():
    """Main function"""
    game_bin = get_game_bin()
    setup_autologin()
    hide_bootloader()
    create_arcade_user()
    setup_screenshots_directory()
    validate_game_binary(game_bin)
    is_windows_game = detect_windows_binary(game_bin)
    if is_windows_game:
        setup_wine_support(game_bin)
    height, width = get_screen_resolution()
    # set_desktop_environments()
    setup_screen_resolution(width, height)
    setup_openbox_keybindings()
    setup_openbox_autostart(Path(game_bin).name,
                            is_windows_game,
                            width,
                            height)
    ensure_arcade_user_owns_home()
    print("Cloister setup completed successfully.")

if __name__ == "__main__":
    main()
