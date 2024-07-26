import json


def read_config():
    """
    Read the configuration file.

    Returns
    -------
    dict
        The configuration file as a dictionary.
    False
        If the configuration file does not exist.
    """
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
            return config
    except FileNotFoundError:
        return False


def create_config():
    """
    Create a new configuration file.
    """
    prompt = "Enter an OAuth token with read access. Check the readme if you don't know how to set this up: "
    oauth_token = input(prompt)
    config = {"token": oauth_token, "subscribed_mods": []}
    save_config(config)


def save_config(config):
    """
    Save the configuration file.

    Parameters
    ----------
    config : dict
        The configuration file as a dictionary.
    """
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)


def get_oauth_token():
    """
    Get the OAuth token from the configuration file.

    Returns
    -------
    str
        The OAuth token.
    None
        If the configuration file does not exist.
    """
    config = read_config()
    return config["token"] if config else None
