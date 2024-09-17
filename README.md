# RoNModsDownloader

[![GitHub Build Status](https://img.shields.io/github/actions/workflow/status/SavageCore/RoNModsDownloader/build.yml?style=flat-square&logo=pytest)](https://github.com/SavageCore/RoNModsDownloader/actions/workflows/build.yml)
[![Code Style: black](https://img.shields.io/badge/code%20style-black-black)](https://pypi.org/project/black/)

A simple Python script to automatically download all the mods you subscribed to on mod.io for the game [Ready or Not](https://mod.io/g/readyornot). Saves you from having to keep the game running to download/update mods. You can also put `.zip` or `.pak` files in the `mods/_manual` folder and they'll be extracted/copied to the game's mods folder as well. If the zip contains a `.sav` (World Gen file) then they'll also be extracted to the correct place.

## Usage

1. Visit Access on [mod.io](https://mod.io/me/access)
1. Generate an API access key if you don't have one yet (you'll also have to accept the terms and conditions)
1. Generate an OAuth access **token**. The token should have read access. You can choose what you want to name it. Make sure you save this as you'll need it later.
1. Download the latest release of this script from the [releases page](https://github.com/SavageCore/RoNModsDownloader/releases), you need both `RoNModsDownloader-win64.exe` and `updater.exe`.
1. Move the .exes to the folder where you want to download the mods to

## Overrides

You may add files with their original folder structure starting from the base game folder to `mods/_overrides`. These files will be copied to the game's folder and the originals saved as `.ron_mods_backup`. This is useful for mods such as no intro where you're replacing the original files with modified ones.

Example:
```
mods\_overrides\ReadyOrNot\Content\Movies\ReadyOrNot_StartupMovie.mp4
```

Will replace the original startup movie with the one you provide. See [here](https://www.nexusmods.com/readyornot/mods/4246) for a ready-to-use blank video file.

## Collections

You may add groups of mods to toggle on/off by creating a folder in `mods/_collections`. These will then show up under the `View Collections` option on the main menu. The folder name will be the name of the collection. Use the arrow keys to select a collection and press Space to toggle it on/off. Press `q` to return to the main menu. These collections will be installed or uninstalled when you run `Install Mods` next.

## Mod Packs

You can pass the `--modpack` flag on startup to point to a mod pack url which will be downloaded and installed when you run `Install Mods`.

The url should route to an address serving a JSON file with the below structure called `rmd.pack` and a folder `mods`, containing all the `.zip` and `.pak` files in the same structure as locally, so `_collections`, `_manual` and `_overrides`.

The subscriptions are the mod.io urls of the mods you want to download.

Collections are defined as above.

There is also the `--purge` flag to remove all mods and collections before installing the mod pack.

```
{
    "name": "SavagePack",
    "version": "0.1.0",
    "description": "SavageCore's Ready or Not Mod Pack",
    "subscriptions": [
        "https://mod.io/g/readyornot/m/fairfax-residence-remake",
        "https://mod.io/g/readyornot/m/lustful-remorse",
    ],
    "collections": {
        "Beat Cop": {
            "enabled": true,
            "mods": [
                "Long Tactical Hider-4453-1-1-1724670588.zip",
                "Los suenos Police Department Uniform-4030-1-2-1722098888.zip",
                "pakchunk99-Mods_OffFacewear_P.pak",
                "pakchunk99-Mods_OffHelmet_P.pak",
                "pakchunk99-Mods_OffVest_P.pak"
            ]
        },
        "John Wick": {
            "enabled": false,
            "mods": [
                "Bullet Time Toggle-4447-1-1-1723212499.zip",
                "Custom Weapon Loader-4099-1-7-1724477498.zip",
                "John Wick Replacement Pack (1.0 UPDATE)-2456-2-0-1702937412.zip",
                "John Wick-4607-1-0-1724673014.zip",
                "pakchunkHIC-DamageRebuff_P.pak",
                "pakchunkHIC-RealDamageRebuff_P.pak",
                "pakchunkHIC-SingleplayerFierce_Arcade_P.pak",
                "TTI G34-4649-1-0-1724675588.zip",
                "TTI GEN12 Shotgun-4597-1-0-1724676623.zip",
                "TTI JW3 MPX-4650-1-0-1724672977.zip",
                "TTI JW4 PitViper-4606-1-0-1724675944.zip",
                "TTI TR1-4609-1-6-1724691221.zip"
            ]
        }
    }
}
```

## Notes

If you have done the setup once then it'll just read the settings from the configuration file it generated and everything should happen automatically. If you want to redo the setup, delete or rename `config.json` and `.auth` and it should show the prompts again.

When you run it a window should pop up where it'll tell you how many subscriptions it found, and it should start downloading and unpacking all the zip files.

If you re-run the script at a later date, it will check your subscriptions for updates and it'll only download mods from new subscriptions or mods which have been updated.
