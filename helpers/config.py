import json

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


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
        create_oauth_token()

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
                return create_oauth_token()

            return oauth_token
    except FileNotFoundError:
        # .auth file does not exist, so prompt for a new OAuth token if we fail to migrate it
        oauth_token = migrate_oauth_token()
        if not oauth_token:
            oauth_token = create_oauth_token()

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
    # """
    # Prompt for and update the OAuth token in the .auth file.
    # """
    prompt = "Enter a new OAuth token with read access: "
    oauth_token = input(prompt)

    # Clear the screen
    print("\033[H\033[J")

    save_oauth_token(oauth_token)

    return oauth_token


def create_oauth_token():
    """
    Login to mod.io and create a new OAuth token.
    Returns
    -------
    str
        The OAuth token.
    """
    print(
        "Getting OAuth token, you'll see a browser window open, please log in manually and wait for the token to be created.\n"
    )
    print("Do not worry, no password is stored, only the OAuth token is saved.\n")
    chrome_options = Options()
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-logging"]
    )  # Suppress driver logs

    service = Service(log_path="nul")  # On Windows use "nul", on Unix use "/dev/null"

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(6)
    driver.get("https://mod.io/login")
    # Wait for login to complete, browser will navigate to "https://mod.io/g" once done
    WebDriverWait(driver, 120).until(EC.url_to_be("https://mod.io/g"))

    print("Login successful, automatically generating OAuth token... TOUCH NOTHING!\n")

    # Once navigated, go to the access page
    driver.get("https://mod.io/me/access")

    # Find input with placeholder "New token name"
    input_element = driver.find_element(
        "xpath", "//input[@placeholder='New token name']"
    )
    # Clear the input field and enter a new token name
    input_element.clear()
    input_element.send_keys("RoNModsDownloader")

    # Get parent element to find the "+" button, which is "up" 5 levels in the DOM
    parent_element = input_element.find_element("xpath", "../../../../../../..")

    # Click the create button
    create_button = parent_element.find_element(By.TAG_NAME, "button")
    create_button.click()

    # Find the new token
    token_created_span = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//span[text()=' Token Created! ']"))
    )
    token_created_span_parent = token_created_span.find_element(By.XPATH, "..")
    token_input = token_created_span_parent.find_element(By.XPATH, ".//input")
    oauth_token = token_input.get_attribute("value")
    driver.quit()
    print("OAuth token created successfully. Continuing...")

    # Save the OAuth token to the .auth file
    save_oauth_token(oauth_token)
    return oauth_token
