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

## Notes

If you have done the setup once then it'll just read the settings from the configuration file it generated and everything should happen automatically. If you want to redo the setup, delete or rename `config.json` and it should show the prompts again.

When you run it a window should pop up where it'll tell you how many subscriptions it found, and it should start downloading and unpacking all the zip files.

If you re-run the script at a later date, it will check your subscriptions for updates and it'll only download mods from new subscriptions or mods which have been updated.

It also acts as a toggle, if on a second run there aren't any new mods subscribed to or added to manual it will uninstall all mods.
