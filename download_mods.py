import argparse
import curses
import hashlib
import os
import shutil
import sys
import zipfile
import zlib

import requests
from packaging.version import parse as parse_version
from tqdm import tqdm

from helpers.config import (
    create_config,
    get_oauth_token,
    read_config,
    save_config,
)
from helpers.github import auto_update
from helpers.modio import (
    get_subscriptions,
    subscribe_to_mod,
    update_subscriptions_config,
    unsubscribe_from_mod,
)
from helpers.modpack import download_folder, list_folder
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
CURRENT_VERSION = "0.7.0"
APP_PATH = os.path.dirname(os.path.abspath(sys.executable))

print("\033[H\033[J")
print_colored_bold(f"\nRoN Mods Downloader ({CURRENT_VERSION})", GREEN)
print("-" * 40)

parser = argparse.ArgumentParser(description="RoN Mods Downloader")
parser.add_argument(
    "--skip-download",
    action="store_true",
    help="Skip downloading mods after checking for updates",
    default=False,
)
parser.add_argument(
    "--purge",
    action="store_true",
    help="Skip downloading mods after checking for updates",
    default=False,
)
args = parser.parse_args()

skip_download = args.skip_download

# If --purge is passed as an argument, remove all mods
if args.purge:
    print_colored("Purging mods...", CYAN)
    # Remove mods/
    if os.path.exists("mods"):
        shutil.rmtree("mods")

        # Recreate mods/ directory
        os.makedirs("mods", exist_ok=True)


# Normalize paths to ensure consistency
def normalize_path(path):
    return os.path.normpath(path).replace("\\", "/")


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
    # If subscribed_mods is not in the config file, return
    if "subscribed_mods" not in config:
        return

    # If subscribed_mods is empty, return
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
                        dst = ""
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
    print_colored("Loading mods...", CYAN)
    mod_files = get_mod_files(mods_down_path)
    existing_mods = os.listdir(mods_dest_path)
    mods_match_status = mods_match(mod_files, mods_dest_path)
    # Get the number of mods to install not including WorldGen or gitkeep files
    mods_quantity = 0
    for mod_file in mod_files:
        if ".gitkeep" in mod_file:
            continue

        if "rmd.pack" in mod_file:
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

    print("\033[H\033[J")
    print("")
    print_colored_bold("Menu", WHITE)
    print("-" * 40)
    if mods_match_status and mods_quantity == mods_installed:
        print("1. Reinstall Mods")
    else:
        print("1. Install Mods")
    print("2. Uninstall Mods")
    print("3. View Collections")
    print("4. Set mod pack URL")
    print("5. Exit")


def view_collections(collections):
    def draw_menu(stdscr, selected_row_idx, scroll_position):
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        if not collections:
            stdscr.addstr(
                0, 0, "No collections found, returning to menu...", curses.color_pair(3)
            )
            stdscr.refresh()
            stdscr.getch()
            return False

        stdscr.addstr(0, 0, "Collections", curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(1, 0, "-" * 40)

        row = 2
        for idx, collection in enumerate(collections):
            if idx < scroll_position:
                continue  # Skip collections above the scroll position

            if row >= max_y - 1:
                break  # Prevent writing outside the terminal window

            collection_text = f"{collection}:"
            enabled_text = (
                "Enabled" if collections[collection]["enabled"] else "Disabled"
            )
            collection_text += f" [{enabled_text}]"

            if len(collection_text) > max_x - 1:
                collection_text = collection_text[: max_x - 4] + "..."

            if idx == selected_row_idx:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(row, 0, collection_text)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(row, 0, collection_text)
            row += 1

        # Info bar
        stdscr.addstr(
            max_y - 1,
            0,
            "Use the arrow keys to choose a collection and spacebar to toggle. Press 'q' to return to menu",
            curses.color_pair(3),
        )

        stdscr.refresh()

    def main(stdscr):
        max_y, _ = stdscr.getmaxyx()

        curses.curs_set(0)
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        current_row = 0
        scroll_position = 0

        while True:
            draw_menu(stdscr, current_row, scroll_position)
            key = stdscr.getch()

            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
                if current_row < scroll_position:
                    scroll_position -= 1
            elif key == curses.KEY_DOWN and current_row < len(collections) - 1:
                current_row += 1
                if current_row >= scroll_position + (max_y - 3):
                    scroll_position += 1
            elif key == ord(" "):
                collection_name = list(collections.keys())[current_row]
                collections[collection_name]["enabled"] = not collections[
                    collection_name
                ]["enabled"]
                save_config(config)
            elif key == ord("q"):
                break

    curses.wrapper(main)


def gather_mods(mods_down_path):
    mod_files = get_mod_files(mods_down_path)

    # Add files in mods_down_path/_manual to mod_files
    manual_path = os.path.join(mods_down_path, "_manual")
    if os.path.exists(manual_path):
        manual_files = []
        for root, dirs, files in os.walk(manual_path):
            for file in files:
                # Construct the relative path from the manual_path
                relative_path = os.path.relpath(
                    os.path.join(root, file), mods_down_path
                )
                manual_files.append(relative_path)

        # Ensure mod_files has the path with subdirectory when extending
        mod_files.extend(manual_files)

    return mod_files


def install_mods(mod_files, mods_dest_path, mods_down_path):
    config = read_config()
    collections = config["collections"]

    # Add any enabled collections to the mod_files list
    for collection in collections:
        if collections[collection]["enabled"]:
            for mod in collections[collection]["mods"]:
                collection_path = os.path.join("_collections", collection)
                # Check if the mod is a zip file and add the .pak files to mod_files
                if mod.endswith(".zip"):
                    with zipfile.ZipFile(
                        os.path.join(mods_down_path, collection_path, mod), "r"
                    ) as zip_ref:
                        entries = zip_ref.infolist()
                        for entry in entries:
                            if entry.is_dir() or not entry.filename.endswith(".pak"):
                                continue
                            mod_files.append(os.path.join(collection_path, mod))
                else:
                    mod_files.append(os.path.join(collection_path, mod))
        else:
            for mod in collections[collection]["mods"]:
                # If the mod is a zip file, remove the .pak files from mod_files
                if mod.endswith(".zip"):
                    file_path = os.path.join(
                        mods_down_path, "_collections", collection, mod
                    )
                    with zipfile.ZipFile(
                        file_path,
                        "r",
                    ) as zip_ref:
                        entries = zip_ref.infolist()
                        for entry in entries:
                            if entry.is_dir() or not entry.filename.endswith(".pak"):
                                continue
                            # Remove the mod from destination path
                            mod_path = os.path.join(mods_dest_path, entry.filename)
                            if os.path.exists(mod_path):
                                os.remove(mod_path)
                else:
                    # Check if the mod is in mods_dest_path and remove it
                    mod_path = os.path.join(mods_dest_path, mod)
                    if os.path.exists(mod_path):
                        os.remove(mod_path)

    print_colored("Extracting mods...", CYAN)
    for mod_file in mod_files:

        # Skip .gitkeep files and also _manual\.gitkeep files
        if ".gitkeep" in mod_file:
            continue

        if "rmd.pack" in mod_file:
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


def uninstall_mods(mods_dest_path, mods_down_path, game_path):
    existing_mods = os.listdir(mods_dest_path)

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


def is_valid_mod_pack_url(url):
    """Check if the mod pack url is valid."""
    try:
        response = requests.get(f"{url}/rmd.pack")
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.exceptions.RequestException as e:
        print_colored(f"Failed to get mod pack file: {e}", RED)
        return False


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

token = get_oauth_token()

print_colored("Checking for downloader updates...", CYAN)
auto_update(REPO, CURRENT_VERSION, APP_PATH, config)

if "mod_pack_url" not in config:
    mod_pack_url = input("Enter the URL of the mod pack (Leave blank to not use one): ")
    config["mod_pack_url"] = mod_pack_url or False
    save_config(config)

if config["mod_pack_url"]:
    print_colored("Checking for mod pack updates...\n", CYAN)
    # If mod_pack_version is not in config, set it to 0.0.0
    if "mod_pack_version" not in config:
        config["mod_pack_version"] = "0.0.0"

    # Check if the mod pack version is different from the current version
    existing = parse_version(config["mod_pack_version"])

    modPackValid = True
    response = None

    # Get the latest release from the mod pack URL
    try:
        response = requests.get(f"{config['mod_pack_url']}/rmd.pack")
    except requests.exceptions.RequestException as e:
        print_colored(f"Failed to check for mod pack updates: {e}", RED)
        modPackValid = False

    if response and response.status_code == 200:
        mp_json_data = response.json()
        latest = parse_version(mp_json_data["version"])

        # If the latest version is greater than the existing version, download the mod pack
        # Also download if the local mods directory is empty
        if latest > existing or not os.listdir(mods_down_path):
            print_colored(
                f"New mod pack version available: {latest} (Current: {existing}). Downloading...\n",
                YELLOW,
            )

            # Update subscriptions
            # Example of json_data:
            # {
            #   "https://mod.io/g/readyornot/m/fairfax-residence-remake",
            #   "https://mod.io/g/readyornot/m/lustful-remorse",
            # }
            # lustful-remorse is the mod_id
            pack_subscriptions = mp_json_data["subscriptions"]
            subscriptions = get_subscriptions()

            # For each subscription, check if it is already subscribed to
            for sub in pack_subscriptions:
                mod_id = sub.split("/")[-1]
                if mod_id not in [s["name_id"] for s in subscriptions]:
                    # Subscribe to the mod
                    subscribed = subscribe_to_mod(mod_id)
                    if not subscribed:
                        print_colored(f"    Failed to subscribe to {mod_id}", RED)
                        print("")
                        sys.exit()

            # Unsubscribe from any mods that are not in the mod pack
            for sub in subscriptions:
                mod_id = sub["name_id"]
                if mod_id not in [url.split("/")[-1] for url in pack_subscriptions]:
                    unsubscribed = unsubscribe_from_mod(mod_id)
                    if not unsubscribed:
                        print_colored(f"    Failed to unsubscribe from {mod_id}", RED)
                        print("")
                        sys.exit()

            # Download the mod folders
            # config['mod_pack_url']}/mods/_collections
            # config['mod_pack_url']}/mods/_manual
            # config['mod_pack_url']}/mods/_overrides

            # Download the collections
            collections_path = os.path.join(mods_down_path, "_collections")
            if not os.path.exists(collections_path):
                os.makedirs(collections_path, exist_ok=True)

            collections_url = f"{config['mod_pack_url']}/mods/_collections/"
            download_folder(collections_url, collections_path)

            # Ensure the collections are in the config file
            if "collections" not in config:
                config["collections"] = {}

            # Create a list of collections to delete
            collections_to_delete = [
                collection
                for collection in config["collections"]
                if collection not in mp_json_data["collections"]
            ]

            # Delete the collections from the config file
            for collection in collections_to_delete:
                del config["collections"][collection]

                # Remove the collection folder
                collection_path = os.path.join(collections_path, collection)
                if os.path.exists(collection_path):
                    shutil.rmtree(collection_path)

            # Compare mp_json_data with config["collections"], ensure the files are the same
            for collection in mp_json_data["collections"]:
                # Check if the collection is in the config file, if not add it
                if collection not in config["collections"]:
                    config["collections"][collection] = {"enabled": False, "mods": []}

                    # Ensure the enabled key matches the mod pack
                    if collection in mp_json_data["collections"]:
                        config["collections"][collection]["enabled"] = mp_json_data[
                            "collections"
                        ][collection]["enabled"]

                    # Add the mods to the collection
                    for mod in mp_json_data["collections"][collection]["mods"]:
                        if mod not in config["collections"][collection]["mods"]:
                            config["collections"][collection]["mods"].append(mod)
                else:
                    # Remove any mods from the collection if the file no longer exists
                    for mod in config["collections"][collection]["mods"]:
                        if mod not in mp_json_data["collections"][collection]["mods"]:
                            config["collections"][collection]["mods"].remove(mod)

            # Download the manual mods
            manual_path = os.path.join(mods_down_path, "_manual")
            if not os.path.exists(manual_path):
                os.makedirs(manual_path, exist_ok=True)

            manual_url = f"{config['mod_pack_url']}/mods/_manual/"
            mod_pack_files = list_folder(manual_url, "_manual")
            download_folder(manual_url, manual_path)

            # Download the overrides
            overrides_path = os.path.join(mods_down_path, "_overrides")
            if not os.path.exists(overrides_path):
                os.makedirs(overrides_path, exist_ok=True)

            overrides_url = f"{config['mod_pack_url']}/mods/_overrides/"
            download_folder(overrides_url, overrides_path)

            # Update the mod pack version in the config file
            config["mod_pack_version"] = str(latest)
            save_config(config)

            print_colored("\nMod pack updated successfully.\n", GREEN)

        else:
            print_colored("No new mod pack updates found.\n", GREEN)

        manual_path = os.path.join(mods_down_path, "_manual")
        manual_url = f"{config['mod_pack_url']}/mods/_manual/"
        mod_pack_files = list_folder(manual_url, "_manual")
        # Remove any manual mods that are no longer in the mod pack
        for root, dirs, files in os.walk(manual_path):
            for mod in files:
                mod_path = os.path.join(root, mod)
                relative_mod_path = os.path.relpath(mod_path, manual_path)
                normalized_mod_path = normalize_path(
                    "mods/_manual/" + relative_mod_path
                )
                # print(f"Checking {normalized_mod_path}")
                if normalized_mod_path not in mod_pack_files:
                    # print(f"Removing {mod_path}")
                    os.remove(mod_path)

                    # Ensure it's removed from ~mods as well
                    # Need to check if it's a zip file and remove the extracted files
                    mod_path = os.path.join(mods_dest_path, mod)
                    if os.path.exists(mod_path):
                        print(f"  Removing {mod}")
                        if mod.endswith(".zip"):
                            with zipfile.ZipFile(mod_path, "r") as zip_ref:
                                for entry in zip_ref.infolist():
                                    if entry.is_dir():
                                        continue
                                    mod_path = os.path.join(
                                        mods_dest_path, entry.filename
                                    )
                                    if os.path.exists(mod_path):
                                        os.remove(mod_path)
                        else:
                            os.remove(mod_path)

        # Remove any collection mods that are no longer in the mod pack, unlike above the mod files are in a subdirectories
        collections_path = os.path.join(mods_down_path, "_collections")
        collections_url = f"{config['mod_pack_url']}/mods/_collections/"
        collection_pack_files = list_folder(collections_url, "_collections")
        for root, dirs, files in os.walk(collections_path):
            for mod in files:
                mod_path = os.path.join(root, mod)
                relative_mod_path = os.path.relpath(mod_path, collections_path)
                normalized_mod_path = normalize_path(
                    "mods/_collections/" + relative_mod_path
                )
                # print(f"Checking {normalized_mod_path}")
                if normalized_mod_path not in collection_pack_files:
                    # print(f"Removing {mod_path}")
                    os.remove(mod_path)

                    # Ensure it's removed from ~mods as well
                    mod_path = os.path.join(mods_dest_path, mod)
                    if os.path.exists(mod_path):
                        print(f"  Removing {mod}")
                        if mod.endswith(".zip"):
                            with zipfile.ZipFile(mod_path, "r") as zip_ref:
                                for entry in zip_ref.infolist():
                                    if entry.is_dir():
                                        continue
                                    mod_path = os.path.join(
                                        mods_dest_path, entry.filename
                                    )
                                    if os.path.exists(mod_path):
                                        os.remove(mod_path)
                        else:
                            os.remove(mod_path)
    else:
        modPackValid = False


subscriptions = get_subscriptions()

# Remove any files that are no longer subscribed to
remove_unsubscribed_mods()
config = update_subscriptions_config(subscriptions)

if not skip_download:
    # Download new mods, checking if they are already downloaded
    print_colored("Downloading mods from mod.io...", CYAN)
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

# Check if "_collections" directory exists
collections_path = os.path.join(mods_down_path, "_collections")

if not os.path.exists(collections_path):
    os.makedirs(collections_path, exist_ok=True)

# Get the list of collections
collections = os.listdir(collections_path)

# Ensure "collections" key exists in the config
if "collections" not in config:
    config["collections"] = {}

# Iterate through the collections
for collection in collections:
    # Ignore .gitkeep files
    if ".gitkeep" in collection:
        continue

    # Get the list of mods in the collection
    collection_mods = os.listdir(os.path.join(collections_path, collection))

    # Check if the collection is in the config file, if not add it
    if collection not in config["collections"]:
        config["collections"][collection] = {"enabled": False, "mods": []}

    # Ensure the enabled key matches the mod pack
    if config["mod_pack_url"] and modPackValid:
        collections_data = mp_json_data["collections"]
        if collection in collections_data:
            config["collections"][collection]["enabled"] = collections_data[collection][
                "enabled"
            ]

    # Add the mods to the collection
    for mod in collection_mods:
        if mod not in config["collections"][collection]["mods"]:
            config["collections"][collection]["mods"].append(mod)

    # Remove any mods from the collection if the file no longer exists
    for mod in config["collections"][collection]["mods"]:
        if mod not in collection_mods:
            config["collections"][collection]["mods"].remove(mod)


# Update the config file
save_config(config)

# Return the list of collections
collections = config["collections"]

mod_files = gather_mods(mods_down_path)

# If there are no mods to install, exit
if not mod_files:
    print_colored("No mods found, nothing to do, exiting...", YELLOW)
    sys.exit()

# Add a menu to choose whether to install or uninstall mods
while True:
    display_menu()
    choice = input("\nEnter your choice [and press enter]: ")

    if choice == "1":
        print("\033[H\033[J")
        install_mods(mod_files, mods_dest_path, mods_down_path)
        input("Press any key to continue...")
        print("\033[H\033[J")
    elif choice == "2":
        print("\033[H\033[J")
        uninstall_mods(mods_dest_path, mods_down_path, game_path)
        input("Press any key to continue...")
        print("\033[H\033[J")
    elif choice == "3":
        print("\033[H\033[J")
        view_collections(collections)
        mod_files = gather_mods(mods_down_path)
    elif choice == "4":
        print("\033[H\033[J")
        mod_pack_url = input("Enter the URL of the mod pack: ")

        if is_valid_mod_pack_url(mod_pack_url):
            print_colored("Valid mod pack URL, updating config...", GREEN)
        else:
            print_colored("Invalid mod pack URL, please try again.", RED)
            continue

        config["mod_pack_url"] = mod_pack_url
        config["mod_pack_version"] = "0.0.0"
        save_config(config)

        # Uninstall all mods ready for the new mod pack
        uninstall_mods(mods_dest_path, mods_down_path, game_path)

        # Remove local mods
        shutil.rmtree(mods_down_path)

        # Press any button to quit
        print("Press any key to quit (then restart afterwards)...")
        input()
        break
    elif choice == "5":
        break
    else:
        print("\033[H\033[J")
        print_colored("Invalid choice, please try again.", RED)

# input("Press Enter to exit...")
