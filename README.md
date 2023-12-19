# RoNModsDownloader

A simple PowerShell script to automatically download all the mods you subscribed to on mod.io for the game [Ready or Not](https://mod.io/g/readyornot). Saves you from having to keep the game running to download/update mods.

## Usage

1. Visit Access on [mod.io](https://mod.io/me/access)
4. Generate API access and OAuth access keys if you don't have them yet (you'll also have to first accept the terms and conditions)
5. Generate an OAuth access *token*. The token should have read access. You can choose what you want to name it. Make sure you save this as you'll need it later.
6. Download the `Download_mods.ps1` file and place it in a folder where you want the downloaded zips of mods to appear
7. Right-click the `Download_mods.ps1` file and select "Run with PowerShell". You will be prompted for the OAuth key from before.

If you have done the setup once then it'll just read the settings from the configuration file it generated and everything should happen automatically. If you want to redo the setup, delete or rename `config.json` and it should show the prompts again.

When you run it a window should pop up where it'll tell you how many subscriptions it found, and it should start downloading and unpacking all the zip files.

If you re-run the script at a later date, it will check your subscriptions for updates and it'll only download mods from new subscriptions or mods which have been updated.
