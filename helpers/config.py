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
    oauth_token = get_oauth_token()
    if not oauth_token:
        update_oauth_token()

    # Create the configuration file
    config = {"subscribed_mods": []}
    save_config(config)
    # Clear the screen
    print("\033[H\033[J")


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
    Get the OAuth token from the .auth file.

    Returns
    -------
    str
        The OAuth token.
    None
        If the .auth file does not exist or is empty.
    """
    oauth_token = None
    try:
        with open(".auth", "r") as f:
            oauth_token = f.read()

            # Migrate the OAuth token if .auth file is empty
            if not oauth_token:
                oauth_token = migrate_oauth_token()

            # Prompt for a new OAuth token if we failed to migrate it
            if not oauth_token:
                return update_oauth_token()

            return oauth_token
    except FileNotFoundError:
        # .auth file does not exist, so prompt for a new OAuth token if we fail to migrate it
        oauth_token = migrate_oauth_token()
        if not oauth_token:
            oauth_token = update_oauth_token()

        return oauth_token


def migrate_oauth_token():
    """
    Migrate the OAuth token from the configuration file to the .auth file.
    """
    config = read_config()
    if config:
        oauth_token = config.get("token")
        if oauth_token:
            save_oauth_token(oauth_token)
            del config["token"]
            save_config(config)
            return oauth_token


def save_oauth_token(oauth_token):
    """
    Save the OAuth token to the .auth file.

    Parameters
    ----------
    oauth_token : str
        The OAuth token.
    """
    with open(".auth", "w") as f:
        f.write(oauth_token)


def update_oauth_token():
    """
    Prompt for and update the OAuth token in the .auth file.
    """
    prompt = "Enter a new OAuth token with read access: "
    oauth_token = input(prompt)

    # Clear the screen
    print("\033[H\033[J")

    save_oauth_token(oauth_token)

    return oauth_token
