#!/usr/bin/env python3

import os
import subprocess
import tempfile
import requests
import shutil
import archinstall
from archinstall.lib.menu import Menu
from archinstall.lib.general import SysCommand


TARGET_ROOT = "/mnt"
GAME_DIR = f"{TARGET_ROOT}/opt/game"


def run(cmd):
    SysCommand(cmd)


def select_game_source():
    options = [
        "Load game from USB",
        "Download game from URL",
        "Skip game install"
    ]
    return Menu("Game setup", options).run()


def find_usb_zip():
    # crude but reliable: look for removable block devices
    result = subprocess.check_output(["lsblk", "-rpno", "NAME,RM"], text=True)
    devices = [line.split()[0] for line in result.splitlines() if line.endswith("1")]

    mounts = []
    for dev in devices:
        mountpoint = tempfile.mkdtemp(prefix="usb-")
        try:
            subprocess.run(["mount", dev, mountpoint], check=True, stdout=subprocess.DEVNULL)
            for f in os.listdir(mountpoint):
                if f.endswith(".zip"):
                    mounts.append((os.path.join(mountpoint, f), mountpoint))
        except Exception:
            shutil.rmtree(mountpoint)
            continue

    if not mounts:
        raise RuntimeError("No ZIP files found on USB devices")

    options = [path for path, _ in mounts]
    choice = Menu("Select game ZIP", options).run()

    for path, mount in mounts:
        if path == choice:
            return path, mount

    raise RuntimeError("Invalid selection")


def download_game_zip():
    url = input("Enter game ZIP URL: ").strip()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    print(f"Downloading {url}...")
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    for chunk in r.iter_content(chunk_size=8192):
        tmp.write(chunk)
    tmp.close()
    return tmp.name


def install_game(zip_path):
    os.makedirs(GAME_DIR, exist_ok=True)
    run(f"unzip -o {zip_path} -d {GAME_DIR}")
    run(f"chmod +x {GAME_DIR}/run.sh")


def main():
    archinstall.check_mirror_reachable()
    archinstall.run_mirror_selection()

    archinstall.ask_for_network()
    archinstall.ask_for_disk_layout()
    archinstall.ask_for_bootloader()
    archinstall.ask_for_hostname()
    archinstall.ask_for_superuser_account()

    game_choice = select_game_source()

    with archinstall.Installer() as installer:
        installer.install_base_system()

        installer.install_packages([
            "networkmanager",
            "iwd",
            "pipewire",
            "pipewire-alsa",
            "pipewire-jack",
            "unzip"
        ])

        installer.enable_service("NetworkManager")

        if game_choice == "Load game from USB":
            zip_path, mount = find_usb_zip()
            install_game(zip_path)
            subprocess.run(["umount", mount])
            shutil.rmtree(mount)

        elif game_choice == "Download game from URL":
            zip_path = download_game_zip()
            install_game(zip_path)
            os.remove(zip_path)

    print("Install complete. Reboot when ready.")


if __name__ == "__main__":
    main()
