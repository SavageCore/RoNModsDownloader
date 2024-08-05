import requests

from helpers.config import get_oauth_token, read_config, save_config, update_oauth_token

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

    try:
        response = requests.get(
            f"{MODIO_API_URL}/me/subscribed?game_id=3791",
            headers={"Authorization": f"Bearer {oauth_token}"},
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 401:
            print("")
            print("Unauthorized access. Please update your OAuth token.")
            update_oauth_token()
            # Clear the screen
            print("\033[H\033[J")
            # Retry the request
            return get_subscriptions()
        else:
            print(f"HTTP error occurred: {http_err}")
        return []
    except Exception as err:
        print(f"An error occurred: {err}")
        return []

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

    save_config(config)

    return config
