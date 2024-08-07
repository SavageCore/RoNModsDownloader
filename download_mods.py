import os
import hashlib
import shutil
import sys
import zlib
import requests
import zipfile

from tqdm import tqdm

from helpers.github import auto_update
from helpers.steam import get_game_install_path
from helpers.config import read_config, create_config, save_config
from helpers.modio import get_subscriptions, update_subscriptions_config


REPO = "SavageCore/RoNModsDownloader"
CURRENT_VERSION = "0.2.4"
APP_PATH = os.path.dirname(os.path.abspath(sys.executable))


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


def extract_mod(file_path, mods_dest_path):
    # Open the zip file and check if any files are not extracted
    with zipfile.ZipFile(file_path, "r") as zip_ref:
        entries = zip_ref.infolist()
        for entry in entries:
            if entry.is_dir():
                continue  # Skip directories

            # Handle nested .pak files
            if entry.filename.endswith(".pak"):
                dst = os.path.join(mods_dest_path, os.path.basename(entry.filename))
            else:
                parts = entry.filename.split("/")
                if len(parts) > 1 and parts[-1].endswith(".pak"):
                    dst = os.path.join(mods_dest_path, parts[-1])
                else:
                    continue  # Skip non-.pak files

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
                print(
                    f"    Skipping {entry.filename} (already extracted and hash matches)"
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
            print("Cleaning up unsubscribed mods...")
            mod_path = os.path.join(mods_down_path, mod_file)

            if os.path.exists(mod_path):
                print(f"  Removing {mod_file}")
                # If the mod is a zip file, extract it and remove the zip file
                if mod_file.endswith(".zip"):
                    with zipfile.ZipFile(mod_path, "r") as zip_ref:
                        print("    Searching for extracted files to remove...")
                        for entry in zip_ref.infolist():
                            dst = os.path.join(mods_dest_path, entry.filename)
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


def mods_match(mod_files, mods_dest_path):
    """Check if the mods in the destination path match the mod files."""
    existing_mods = {
        os.path.basename(f.path): get_crc(f.path)
        for f in os.scandir(mods_dest_path)
        if f.is_file() and f.name.endswith(".pak")
    }
    for mod_file in mod_files:
        if os.path.basename(mod_file) == ".gitkeep":
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
    print("Ready or Not not found in Steam library.")
    exit()

mods_dest_path = os.path.join(game_path, "ReadyOrNot", "Content", "Paks", "~mods")
# Make directory if it doesn't exist
os.makedirs(mods_dest_path, exist_ok=True)

mods_down_path = "mods"

# If the mods directory doesn't exist, look for "zips" directory instead
if not os.path.exists(mods_down_path):
    mods_down_path = "zips"

# If read_config returns False, create a new config file
if not read_config():
    create_config()

config = read_config()

token = config.get("token")
if not token:
    create_config()

print("Checking for updates...")
auto_update(REPO, CURRENT_VERSION, APP_PATH, config)

subscriptions = get_subscriptions()

# Remove any files that are no longer subscribed to)
remove_unsubscribed_mods()
config = update_subscriptions_config(subscriptions)

# Download new mods, checking if they are already downloaded
print("Downloading mods...")
for sub in subscriptions:
    mod_id = sub["name_id"]
    mod_file = sub["modfile"]["filename"]
    mod_md5 = sub["modfile"]["filehash"]["md5"]
    mod_file_path = os.path.join(mods_down_path, mod_file)

    if mod_file not in os.listdir(mods_down_path) or mod_md5 != get_md5(mod_file_path):
        download_mod(mod_id)
    else:
        print(
            f"  Skipping download of {mod_file} (already downloaded and hash matches)"
        )

# Extract new mods, checking if they are already extracted
mod_files = os.listdir(mods_down_path)
existing_mods = os.listdir(mods_dest_path)
# Remove directories from mod_files
mod_files = [f for f in mod_files if not os.path.isdir(os.path.join(mods_down_path, f))]
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
    print("No mods found, nothing to do, exiting...")
    sys.exit()

print("")
if mods_match(mod_files, mods_dest_path):
    print("Uninstalling mods...")
    for mod_file in existing_mods:
        print(f"  Removing {mod_file}")
        dst = os.path.join(mods_dest_path, mod_file)
        os.remove(dst)

    # Uninstall overrides
    overrides_path = os.path.join(mods_down_path, "_overrides")
    if os.path.exists(overrides_path):
        print("Restoring overrides...")
        for root, _, files in os.walk(overrides_path):
            for file in files:
                if file == ".gitkeep":
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
else:
    print("Extracting mods...")
    for mod_file in mod_files:
        print(f"  {mod_file}")
        mod_path = os.path.join(mods_down_path, mod_file)
        if mod_file.endswith(".zip"):
            extract_mod(mod_path, mods_dest_path)
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
                print(f"    Skipping {mod_name} (already copied and hash matches)")

    overrides_path = os.path.join(mods_down_path, "_overrides")

    if os.path.exists(overrides_path):
        print("")
        print("Replacing overrides...")
        for root, _, files in os.walk(overrides_path):
            for file in files:
                if file == ".gitkeep":
                    continue

                src = os.path.join(root, file)
                dst = os.path.join(
                    game_path, os.path.relpath(src, start=overrides_path)
                )
                if os.path.exists(dst):
                    print(f"  Backing up {os.path.relpath(dst, start=game_path)}")
                    shutil.move(dst, dst + ".ron_mods_backup")
                print(f"  Replacing {os.path.relpath(dst, start=game_path)}")
                shutil.copy(src, dst)
        print("")


input("Press Enter to exit...")
