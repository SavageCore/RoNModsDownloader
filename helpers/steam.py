import os
import winreg as reg
import vdf


def get_steam_install_location():
    """The function `get_steam_install_location` retrieves the installation location of Steam from the
    Windows registry.

    Returns
    -------
        The function `get_steam_install_location` returns the installation location of Steam as a
    string.

    """
    steam_key = reg.OpenKey(
        reg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Wow6432Node\Valve\Steam",
    )

    steam_install_location = reg.QueryValueEx(steam_key, "InstallPath")[0]

    reg.CloseKey(steam_key)

    return steam_install_location


def get_game_install_path(app_id):
    """
    Searches for the installation path of a game using the provided app ID in Steam directories.

    Parameters
    ----------
    app_id : str
        The Steam application ID of the game.

    Returns
    -------
    str or None
        The installation path of the game if found, otherwise None.
    """
    steam_install_location = get_steam_install_location()
    steam_apps_path = os.path.join(steam_install_location, "steamapps")

    # Check the main steamapps directory first
    install_path = _check_app_manifest(steam_apps_path, app_id)
    if install_path:
        return install_path

    # Check the library folders
    library_folders_file = os.path.join(steam_apps_path, "libraryfolders.vdf")
    if os.path.exists(library_folders_file):
        with open(library_folders_file, "r") as f:
            library_folders = vdf.load(f)["libraryfolders"]

        for key, library in library_folders.items():
            if key == "0":
                continue

            library_path = os.path.join(library["path"], "steamapps")
            install_path = _check_app_manifest(library_path, app_id)
            if install_path:
                return install_path

    return None


def _check_app_manifest(steam_apps_path, app_id):
    """
    Helper method to check for the app manifest and return the installation path if found.

    Parameters
    ----------
    steam_apps_path : str
        Path to the steamapps directory.
    app_id : str
        The Steam application ID of the game.

    Returns
    -------
    str or None
        The installation path of the game if found, otherwise None.
    """
    manifest_file = os.path.join(steam_apps_path, f"appmanifest_{app_id}.acf")
    if os.path.exists(manifest_file):
        with open(manifest_file, "r") as f:
            manifest = vdf.load(f)
            install_location = os.path.join(
                steam_apps_path, "common", manifest["AppState"]["installdir"]
            )
            if os.path.exists(install_location):
                return install_location
    return None
