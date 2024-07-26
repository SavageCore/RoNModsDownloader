import json
import requests

from helpers.config import get_oauth_token, read_config

MODIO_API_URL = "https://api.mod.io/v1"


def get_subscriptions():
    """
    Retrieves the list of subscribed mods from the mod.io API.

    Returns
    -------
    list of dict
        A list of dictionaries containing information about the subscribed mods.
    """
    oauth_token = get_oauth_token()

    response = requests.get(
        f"{MODIO_API_URL}/me/subscribed?game_id=3791",
        headers={"Authorization": f"Bearer {oauth_token}"},
    )
    response.raise_for_status()

    subscriptions = response.json()["data"]

    return subscriptions


def update_subscriptions_config(subscriptions):
    """
    Updates the configuration file with the subscribed mods.

    Parameters
    ----------
    subscriptions : list of dict
        A list of dictionaries containing information about the subscribed mods.
    """

    config = read_config()
    config["subscribed_mods"] = {}

    for sub in subscriptions:
        config["subscribed_mods"][sub["name_id"]] = {
            "md5": sub["modfile"]["filehash"]["md5"],
            "file": sub["modfile"]["filename"],
            "download": sub["modfile"]["download"]["binary_url"],
        }

    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)
