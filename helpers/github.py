import os
import subprocess
import sys
from datetime import datetime, timedelta

import requests
import semver

from helpers.config import save_config
from helpers.print_colored import GREEN, RED, YELLOW, print_colored


def check_for_update(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url)
    if response.status_code == 200:
        latest_release = response.json()
        return (
            latest_release["tag_name"],
            latest_release["assets"][0]["browser_download_url"],
        )
    return None, None


def download_update(download_url, output_path):
    response = requests.get(download_url, stream=True)
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def auto_update(repo, current_version, app_path, config):
    print("")
    updater_path = os.path.join(app_path, "updater.exe")

    if not os.path.exists(updater_path):
        print_colored("Updater not found. Downloading latest version...", YELLOW)
        print("")
        download_update(
            "https://github.com/SavageCore/RoNModsDownloader/releases/latest/download/updater.exe",
            updater_path,
        )

    if not isinstance(config, dict):
        config = {}

    last_update_check = config.get("last_update_check")
    if last_update_check:
        last_update_check = datetime.fromisoformat(last_update_check)
        time_since_last_check = datetime.now() - last_update_check
        if time_since_last_check < timedelta(hours=1):
            time_until_next_check = 60 - (time_since_last_check.seconds // 60)
            print_colored(
                f"Update check skipped to avoid rate limiting. Try again in {time_until_next_check} minutes.",
                YELLOW,
            )
            print("")
            return

    latest_version, download_url = check_for_update(repo)
    if latest_version is None:
        print_colored("Failed to check for updates.", RED)
        print("")
        return
    latest_version = latest_version[1:]

    if semver.compare(current_version, latest_version) == -1:
        print_colored(
            f"New version {latest_version} available. Downloading update...",
            GREEN,
        )
        print("")

        # Download the latest updater
        download_update(
            "https://github.com/SavageCore/RoNModsDownloader/releases/latest/download/updater.exe",
            updater_path,
        )

        temp_path = os.path.join(app_path, "update_temp.exe")
        download_update(download_url, temp_path)

        print_colored("Update downloaded. Restarting...", GREEN)
        config["last_update_check"] = datetime.now().isoformat()
        save_config(config)

        subprocess.Popen([updater_path, temp_path])
        sys.exit(0)
    else:
        print_colored("No updates available.", GREEN)
        print("")

    config["last_update_check"] = datetime.now().isoformat()
    save_config(config)
