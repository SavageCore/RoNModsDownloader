import os
import hashlib
import zlib
import requests
import zipfile

from tqdm import tqdm

from helpers.steam import get_game_install_path
from helpers.config import read_config, create_config, save_config
from helpers.modio import get_subscriptions, update_subscriptions_config


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
            dst = os.path.join(mods_dest_path, entry.filename)

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
    for sub in config["subscribed_mods"].values():
        mod_file = sub["file"]

        if mod_file not in [sub["modfile"]["filename"] for sub in subscriptions]:
            zip_path = os.path.join(mods_down_path, mod_file)

            if os.path.exists(zip_path):
                print(f"  Removing {mod_file}")
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    print("  Searching for extracted files to remove...")
                    for entry in zip_ref.infolist():
                        dst = os.path.join(mods_dest_path, entry.filename)
                        if os.path.exists(dst):
                            print(f"    Removing {entry.filename}")
                            os.remove(dst)
                        # Remove the containing folder if it is empty
                        folder = os.path.dirname(dst)
                        if not os.listdir(folder):
                            os.rmdir(folder)

                # Remove the zip file
                os.remove(zip_path)
            else:
                print(f"    {mod_file} not found")


# Get game install path
game_path = get_game_install_path("1144200")
if not game_path:
    print("Ready or Not not found in Steam library.")
    exit()

mods_dest_path = os.path.join(game_path, "ReadyOrNot", "Content", "Paks", "~mods")
mods_down_path = "zips"

# If read_config returns False, create a new config file
if not read_config():
    create_config()

config = read_config()
subscriptions = get_subscriptions()

# Remove any files that are no longer subscribed to)
remove_unsubscribed_mods()
update_subscriptions_config(subscriptions)

# Download new mods, checking if they are already downloaded
if len(subscriptions) == 0:
    print("No mods found in subscriptions, nothing to do, exiting...")
    exit()

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

mods_match = True
for mod_file in mod_files:
    with zipfile.ZipFile(os.path.join(mods_down_path, mod_file), "r") as zip_ref:
        for entry in zip_ref.infolist():
            dst = os.path.join(mods_dest_path, entry.filename)
            if not os.path.exists(dst) or get_crc(dst) != entry.CRC:
                mods_match = False
                break

if mods_match:
    print("Uninstalling mods...")
    for mod_file in existing_mods:
        print(f"  Removing {mod_file}")
        dst = os.path.join(mods_dest_path, mod_file)
        os.remove(dst)
else:
    if mod_files:
        print("Extracting mods...")

        for mod_file in mod_files:
            print(f"  {mod_file}")

            mod_path = os.path.join(mods_down_path, mod_file)
            extract_mod(mod_path, mods_dest_path)
            # # Open the zip file and check if any files are not extracted
            # with zipfile.ZipFile(mod_path, "r") as zip_ref:
            #     for entry in zip_ref.infolist():
            #         dst = os.path.join(mods_dest_path, entry.filename)
            #         # If the file is not extracted or the hash does not match, extract it
            #         if not os.path.exists(dst) or get_crc(dst) != entry.CRC:
            #             # print(f"    Extracting {entry.filename}")
            #             extract_mod(mod_path, mods_dest_path)
            #         else:
            #             print(
            #                 f"    Skipping {entry.filename} (already extracted and hash matches)"
            #             )
