import hashlib
import os
import shutil
import sys
import zipfile
import zlib

import requests
from tqdm import tqdm

from helpers.config import create_config, read_config, save_config
from helpers.github import auto_update
from helpers.modio import get_subscriptions, update_subscriptions_config
from helpers.print_colored import (
    CYAN,
    GREEN,
    RED,
    WHITE,
    YELLOW,
    print_colored,
    print_colored_bold,
)
from helpers.steam import get_game_install_path

REPO = "SavageCore/RoNModsDownloader"
CURRENT_VERSION = "0.4.4"
APP_PATH = os.path.dirname(os.path.abspath(sys.executable))

print("\033[H\033[J")
print_colored_bold(f"\nRoN Mods Downloader ({CURRENT_VERSION})", GREEN)
print("-" * 40)

skip_download = False

if len(sys.argv) > 1 and sys.argv[1] == "--skip-download":
    skip_download = True


def get_md5(file_path):
    """
    Calculate the MD5 hash of a file.

    Parameters
    ----------
    file_path : str
        The path to the file.

    Returns
    -------
    str
        The MD5 hash of the file.
    None
        If the file does not exist.
    """
    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        md5 = hashlib.md5()
        while chunk := f.read(8192):
            md5.update(chunk)
        return md5.hexdigest()


def get_crc(file_path):
    """
    Calculate the CRC32 hash of a file.

    Parameters
    ----------
    file_path : str
        The path to the file.

    Returns
    -------
    str
        The CRC32 hash of the file.
    None
        If the file does not exist.
    """
    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        crc = 0
        while chunk := f.read(8192):
            crc = zlib.crc32(chunk, crc)
        return crc


def download_mod(mod_id):
    """
    Download a mod from mod.io.

    Parameters
    ----------
    mod_id : int
        The ID of the mod to download.
    """
    if mod_id in config["subscribed_mods"]:
        mod_info = config["subscribed_mods"][mod_id]
        download_url = mod_info["download"]
        file_path = os.path.join(mods_down_path, mod_info["file"])

        # Make directory if it doesn't exist
        os.makedirs(mods_down_path, exist_ok=True)

        # Download the file in chunks, showing progress
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            chunk_size = 8192
            with open(file_path, "wb") as f, tqdm(
                desc="  " + mod_info["file"],
                total=total_size,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    size = f.write(chunk)
                    bar.update(size)

            contents = []

            # Get zip file contents
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                for entry in zip_ref.infolist():
                    contents.append(entry.filename)

            # Save contents to config
            mod_info["contents"] = contents

            # Update the config file
            config["subscribed_mods"][mod_id] = mod_info
            save_config(config)


def extract_mod(file_path, mods_dest_path, savegames_dest_path):
    # Open the zip file and check if any files are not extracted
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        entries = zip_ref.infolist()
        for entry in entries:
            if entry.is_dir():
                continue  # Skip directories

            # Determine destination based on file extension
            if entry.filename.endswith(".pak"):
                dst = os.path.join(mods_dest_path, os.path.basename(entry.filename))
            elif entry.filename.endswith(".sav"):
                dst = os.path.join(
                    savegames_dest_path, os.path.basename(entry.filename)
                )
            else:
                # Check if the file is nested and contains .pak or .sav files
                parts = entry.filename.split("/")
                if len(parts) > 1 and parts[-1].endswith(".pak"):
                    dst = os.path.join(mods_dest_path, parts[-1])
                elif len(parts) > 1 and parts[-1].endswith(".sav"):
                    dst = os.path.join(savegames_dest_path, parts[-1])
                else:
                    continue  # Skip non-.pak and non-.sav files

            # Check if the file needs to be extracted
            if not os.path.exists(dst) or get_crc(dst) != entry.CRC:
                with zip_ref.open(entry) as source, open(dst, "wb") as target:
                    total_size = entry.file_size
                    with tqdm(
                        total=total_size,
                        desc=f"    Extracting {entry.filename}",
                        unit="iB",
                        unit_scale=True,
                        unit_divisor=1024,
                    ) as file_bar:
                        for chunk in iter(lambda: source.read(8192), b""):
                            target.write(chunk)
                            file_bar.update(len(chunk))
            else:
                print_colored(
                    f"    Skipping {entry.filename} (already extracted and hash matches)",
                    YELLOW,
                )
        print("")


def remove_unsubscribed_mods():
    """
    Remove any mods that are no longer subscribed to.
    """
    if not config["subscribed_mods"]:
        return

    for sub in config["subscribed_mods"].values():
        mod_file = sub["file"]

        if mod_file not in [sub["modfile"]["filename"] for sub in subscriptions]:
            print_colored("Cleaning up unsubscribed mods...", CYAN)
            mod_path = os.path.join(mods_down_path, mod_file)

            if os.path.exists(mod_path):
                print(f"  Removing {mod_file}")
                # If the mod is a zip file, extract it and remove the zip file
                if mod_file.endswith(".zip"):
                    with zipfile.ZipFile(mod_path, "r") as zip_ref:
                        print("    Searching for extracted files to remove...")
                        for entry in zip_ref.infolist():
                            # Check if the file is a .pak or .sav file
                            if entry.filename.endswith(".pak"):
                                dst = os.path.join(mods_dest_path, entry.filename)
                            elif entry.filename.endswith(".sav"):
                                dst = os.path.join(savegames_dest_path, entry.filename)
                            if os.path.exists(dst):
                                print(f"      Removing {entry.filename}")
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                else:
                                    os.remove(dst)
                            # # Remove the containing folder if it is empty
                            # folder = os.path.dirname(dst)
                            # if not os.listdir(folder):
                            #     os.rmdir(folder)

                # Remove the mod file
                os.remove(mod_path)
            else:
                print(f"    {mod_file} not found")
            print("")


def get_mod_files(mods_down_path):
    mod_files = os.listdir(mods_down_path)
    # Remove directories from mod_files
    mod_files = [
        f for f in mod_files if not os.path.isdir(os.path.join(mods_down_path, f))
    ]

    return mod_files


def display_menu():
    existing_mods = os.listdir(mods_dest_path)
    mods_match_status = mods_match(mod_files, mods_dest_path)
    # Get the number of mods to install not including WorldGen or gitkeep files
    mods_quantity = 0
    for mod_file in mod_files:
        if ".gitkeep" in mod_file:
            continue

        if "WorldGen" in mod_file:
            continue

        # If the file is a zip, count the number of .pak files inside
        if mod_file.endswith(".zip"):
            with zipfile.ZipFile(
                os.path.join(mods_down_path, mod_file), "r"
            ) as zip_ref:
                entries = zip_ref.infolist()
                for entry in entries:
                    if entry.is_dir() or not entry.filename.endswith(".pak"):
                        continue
                    mods_quantity += 1
        else:
            mods_quantity += 1

    mods_installed = len(existing_mods)

    print("")
    print_colored_bold("Menu", WHITE)
    print("-" * 40)
    if mods_match_status and mods_quantity == mods_installed:
        print("1. Reinstall Mods")
    else:
        print("1. Install Mods")
    print("2. Uninstall Mods")
    print("3. Exit")


def install_mods(mod_files, mods_dest_path):
    print_colored("Extracting mods...", CYAN)
    for mod_file in mod_files:

        # Skip .gitkeep files and also _manual\.gitkeep files
        if ".gitkeep" in mod_file:
            continue

        print_colored_bold(f" {mod_file}", WHITE)
        mod_path = os.path.join(mods_down_path, mod_file)
        if mod_file.endswith(".zip"):
            extract_mod(mod_path, mods_dest_path, savegames_dest_path)
        else:
            mod_name = os.path.basename(mod_file)

            existing_mods = {
                os.path.basename(f.path): get_crc(f.path)
                for f in os.scandir(mods_dest_path)
                if f.is_file() and f.name.endswith(".pak")
            }

            if (
                mod_name not in existing_mods
                or get_crc(mod_path) != existing_mods[mod_name]
            ):
                shutil.copy(mod_path, mods_dest_path)
            else:
                print_colored(
                    f"    Skipping {mod_name} (already copied and hash matches)", YELLOW
                )
                print("")

    overrides_path = os.path.join(mods_down_path, "_overrides")

    if os.path.exists(overrides_path):
        print("")
        print_colored("Replacing overrides...", CYAN)
        for root, _, files in os.walk(overrides_path):
            for file in files:
                if ".gitkeep" in file:
                    continue

                src = os.path.join(root, file)
                dst = os.path.join(
                    game_path, os.path.relpath(src, start=overrides_path)
                )

                print_colored_bold(f" {os.path.relpath(dst, start=game_path)}", WHITE)

                # Backup the file if it exists, unless it's already backed up
                if os.path.exists(dst) and not os.path.exists(dst + ".ron_mods_backup"):
                    print(f"  Backing up {os.path.relpath(dst, start=game_path)}")
                    shutil.move(dst, dst + ".ron_mods_backup")
                # Replace the file if it doesn't exist or the hash doesn't match
                if not os.path.exists(dst) or get_crc(src) != get_crc(dst):
                    print(f"  Replacing {os.path.relpath(dst, start=game_path)}")
                    shutil.copy(src, dst)
                else:
                    print_colored(
                        f"  Skipping {os.path.relpath(dst, start=game_path)} (already replaced and hash matches)",
                        YELLOW,
                    )
                print("")
        print("")


def uninstall_mods(existing_mods, mods_dest_path, mods_down_path, game_path):
    if not existing_mods:
        print_colored("No mods installed, nothing to do.", YELLOW)
    else:
        print_colored("Uninstalling mods...", CYAN)
        for mod_file in existing_mods:
            print(f"  Removing {mod_file}")
            dst = os.path.join(mods_dest_path, mod_file)
            os.remove(dst)

    # Uninstall overrides
    overrides_path = os.path.join(mods_down_path, "_overrides")
    if os.path.exists(overrides_path):
        print_colored("Restoring overrides...", CYAN)
        for root, _, files in os.walk(overrides_path):
            for file in files:
                if ".gitkeep" in file:
                    continue

                dst = os.path.join(
                    game_path,
                    os.path.relpath(os.path.join(root, file), start=overrides_path),
                )

                if os.path.exists(dst + ".ron_mods_backup"):
                    if os.path.exists(dst):
                        print(f"  Removing {os.path.relpath(dst, start=game_path)}")
                        os.remove(dst)

                    print(
                        f"  Restoring backup of {os.path.relpath(dst, start=game_path)}"
                    )
                    shutil.move(dst + ".ron_mods_backup", dst)
        print("")


def mods_match(mod_files, mods_dest_path):
    """Check if the mods in the destination path match the mod files."""
    existing_mods = {
        os.path.basename(f.path): get_crc(f.path)
        for f in os.scandir(mods_dest_path)
        if f.is_file() and f.name.endswith(".pak")
    }
    for mod_file in mod_files:
        if ".gitkeep" in os.path.basename(mod_file):
            continue

        if mod_file.endswith(".zip"):
            with zipfile.ZipFile(
                os.path.join(mods_down_path, mod_file), "r"
            ) as zip_ref:
                entries = zip_ref.infolist()
                for entry in entries:
                    if entry.is_dir() or not entry.filename.endswith(".pak"):
                        continue
                    mod_name = os.path.basename(entry.filename)
                    if mod_name not in existing_mods:
                        return False
        else:
            mod_name = os.path.basename(mod_file)
            if mod_name not in existing_mods:
                return False
    return True


# Get game install path
game_path = get_game_install_path("1144200")
if not game_path:
    print_colored("Ready or Not not found in Steam library.", RED)
    exit()

mods_dest_path = os.path.join(game_path, "ReadyOrNot", "Content", "Paks", "~mods")
savegames_dest_path = os.path.join(
    os.getenv("LOCALAPPDATA"), "ReadyOrNot", "Saved", "SaveGames"
)
# Make directory if it doesn't exist
os.makedirs(mods_dest_path, exist_ok=True)

mods_down_path = "mods"

# If the mods directory doesn't exist, look for "zips" directory instead
if not os.path.exists(mods_down_path):
    mods_down_path = "zips"

if not os.path.exists(mods_down_path):
    mods_down_path = "mods"
    os.makedirs(mods_down_path, exist_ok=True)

# If read_config returns False, create a new config file
if not read_config():
    create_config()

config = read_config()

token = config.get("token")
if not token:
    create_config()

print_colored("Checking for downloader updates...", CYAN)
auto_update(REPO, CURRENT_VERSION, APP_PATH, config)

subscriptions = get_subscriptions()

# Remove any files that are no longer subscribed to)
remove_unsubscribed_mods()
config = update_subscriptions_config(subscriptions)

if not skip_download:
    # Download new mods, checking if they are already downloaded
    print_colored("Downloading mods...", CYAN)
    print("")
    for sub in subscriptions:
        mod_id = sub["name_id"]
        mod_file = sub["modfile"]["filename"]
        mod_md5 = sub["modfile"]["filehash"]["md5"]
        mod_file_path = os.path.join(mods_down_path, mod_file)

        if mod_file not in os.listdir(mods_down_path) or mod_md5 != get_md5(
            mod_file_path
        ):
            download_mod(mod_id)
        else:
            print_colored(
                f"  Skipping download of {mod_file} (already downloaded and hash matches)",
                YELLOW,
            )
    print("")

print_colored("Loading mods...", CYAN)
# Extract new mods, checking if they are already extracted
mod_files = get_mod_files(mods_down_path)
existing_mods = os.listdir(mods_dest_path)
# Add files in mods_down_path/_manual to mod_files
manual_path = os.path.join(mods_down_path, "_manual")
if os.path.exists(manual_path):
    manual_files = os.listdir(manual_path)
    # Enter any subdirectories and add the files to mod_files
    for f in manual_files:
        if os.path.isdir(os.path.join(manual_path, f)):
            manual_files.extend(
                [
                    os.path.join(f, sub_f)
                    for sub_f in os.listdir(os.path.join(manual_path, f))
                ]
            )
    # Remove directories from manual_files
    manual_files = [
        f for f in manual_files if not os.path.isdir(os.path.join(manual_path, f))
    ]
    # Ensure mod_files has the path with subdirectory when extending
    manual_files = [os.path.join("_manual", f) for f in manual_files]
    mod_files.extend(manual_files)

# If there are no mods to install, exit
if not mod_files:
    print_colored("No mods found, nothing to do, exiting...", YELLOW)
    sys.exit()

# Add a menu to choose whether to install or uninstall mods
while True:
    display_menu()
    choice = input("Enter your choice: ")

    if choice == "1":
        print("\033[H\033[J")
        install_mods(mod_files, mods_dest_path)
    elif choice == "2":
        print("\033[H\033[J")
        uninstall_mods(existing_mods, mods_dest_path, mods_down_path, game_path)
    elif choice == "3":
        break
    else:
        print("\033[H\033[J")
        print_colored("Invalid choice, please try again.", RED)

# input("Press Enter to exit...")
