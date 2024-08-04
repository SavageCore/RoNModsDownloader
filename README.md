# RoNModsDownloader

[![GitHub Build Status](https://img.shields.io/github/actions/workflow/status/SavageCore/RoNModsDownloader/build.yml?style=flat-square&logo=pytest)](https://github.com/SavageCore/RoNModsDownloader/actions/workflows/build.yml)
[![Code Style: black](https://img.shields.io/badge/code%20style-black-black)](https://pypi.org/project/black/)

A simple PowerShell script to automatically download all the mods you subscribed to on mod.io for the game [Ready or Not](https://mod.io/g/readyornot). Saves you from having to keep the game running to download/update mods.

## Usage

1. Visit Access on [mod.io](https://mod.io/me/access)
1. Generate API access and OAuth access keys if you don't have them yet (you'll also have to accept the terms and conditions)
1. Generate an OAuth access **token**. The token should have read access. You can choose what you want to name it. Make sure you save this as you'll need it later.
1. Download the latest release of this script from the [releases page](https://github.com/SavageCore/RoNModsDownloader/releases)
1. Move the .exe file to the folder where you want to download the mods to

## Requirements

If you have done the setup once then it'll just read the settings from the configuration file it generated and everything should happen automatically. If you want to redo the setup, delete or rename `config.json` and it should show the prompts again.

When you run it a window should pop up where it'll tell you how many subscriptions it found, and it should start downloading and unpacking all the zip files.

If you re-run the script at a later date, it will check your subscriptions for updates and it'll only download mods from new subscriptions or mods which have been updated.
