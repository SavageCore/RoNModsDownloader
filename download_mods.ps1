Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem

# Used to simplify y/n prompts further in the script
function Confirm-User($msg, $default = 'Y') {
	$choices = '&Yes', '&No'
	if ($default -eq 'N') {
		$choices = '&No', '&Yes'
	}
	$decision = $host.UI.PromptForChoice("", $msg, $choices, 0)
	if ($decision -eq 0 -and $default -eq 'Y') {
		return $true
	}
 elseif ($decision -eq 0 -and $default -eq 'N') {
		return $false
	}
 elseif ($decision -eq 1 -and $default -eq 'Y') {
		return $false
	}
 elseif ($decision -eq 1 -and $default -eq 'N') {
		return $true
	}
}

if (Test-Path config.json) {
	Write-Output "Reading settings from config.json."
	Write-Output "If you wish to change these settings, delete the config file and run the script again."
	Write-Output "" ""
	$config = Get-Content config.json | ConvertFrom-Json
}
else {
	$config = @{}

	Write-Output "No configuration file found. Let's set up a new one."
	$dest = "C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not\ReadyOrNot\Content\Paks\~mods"

	$unpack = Confirm-User "Do you wish to automatically unpack or install downloaded/updated mods?"

	if ($unpack) {
		Write-Output "The default installation path is: $dest"

		if (-not(Confirm-User "Install/unpack mods to that location?")) {
			Write-Output "Enter the path to the desired location."
			$dest = Read-Host "Desired location"
		}
		if (-not(Test-Path $dest)) {
			Mkdir $dest
		}
	}

	Write-Output "Enter an OAuth token with read access."
	Write-Output "Check the readme if you don't know how to set this up".
	do {
		$tok = Read-Host "OAuth token"
		if ($tok.length -lt 1000) {
			Write-Output "This doesn't seem to be a valid OAuth token. Make sure to copy an OAuth token, NOT an API access key"
			Write-Output "(a proper OAuth token should be much longer than the value you entered)"
		}
	}
	while ($tok.length -lt 1000)
	Write-Output "Thank you, that should be everything I need."

	$config.token = $tok
	$config.unpack = $unpack
	$config.destination = $dest

	# Write initial configuration to the config file
	# (so that the user doesn't have to go trough the setup again if the script doesn't run completely)
	$config | ConvertTo-Json | Set-Content config.json

	Write-Output "I'll now start downloading all your subscribed mods."
	Write-Output '' '' '' ''
}

$token = $config.token
$destination = $config.destination
$unpack = $config.unpack

if (-not(Test-Path zips)) {
	Mkdir zips
}

Write-Output "Checking subscriptions..."
$sublist_json = Invoke-WebRequest -UseBasicParsing -URI https://api.mod.io/v1/me/subscribed?game_id=3791 -Method GET -Headers @{"Authorization" = "Bearer ${token}"; "Accept" = "application/json" }
$sublist = ConvertFrom-Json $sublist_json.Content

$len = $sublist.data.length
[string]$len_str = $len
Write-Output "Found $len_str subscription(s)."

for ($i = 0; $i -lt $len; $i++) {
	$sub = $sublist.data[$i]
	$subname = $sub.name
	Write-Output ''
	Write-Output "Requesting info for '$subname'..."
	[string]$modid = $sub.id
	$mod_json = Invoke-WebRequest -UseBasicParsing -URI https://api.mod.io/v1/games/3791/mods/${modid}/files -Method GET -Headers @{"Authorization" = "Bearer ${token}"; "Accept" = "application/json" }
	$mod = ConvertFrom-Json $mod_json.Content

	# get latest version in remaining files and keep only files matching that version
	$mod.data = @($mod.data)
	$lastver = ($mod.data | Select-Object -ExpandProperty version | Measure-Object -Maximum).Maximum
	$mod.data = $mod.data | Where-Object { $_.version -ge $lastver }
	$mod.data = @($mod.data)
	Write-Output "  Latest version: $lastver"

	# Write data about this sub to config
	$name = $sub.name_id

	$update = $true
	# If config doesn't have a subscriptions entry, add it
	if ($null -eq $config.subscriptions) {
		$config | Add-Member -Name subscriptions -Value @{} -MemberType NoteProperty
	}

	# If config doesn't have a subscription entry under subscrriptions, add it
	if ($null -eq $config.subscriptions.${name}) {
		$config.subscriptions | Add-Member -Name ${name} -Value @{} -MemberType NoteProperty
	}

	if ($mod.data.filehash.md5 -eq $config.subscriptions.${name}.md5) {
		$update = $false # already up to date
		Write-Output "  Subscription is up to date, checking if files match..."
	}

	$config.subscriptions.${name}.md5 = $mod.data.filehash.md5

	$datalen = $mod.data.length
	[string]$datalen_str = $datalen
	$fileStr = if ($datalen_str -gt 1) { "files" } else { "file" }
	Write-Output "  Subscription contains $datalen_str $fileStr."

	for ($j = 0; $j -lt $datalen; $j++) {
		$data = $mod.data[$j]
		$file = $data.filename

		# If config doesn't have a file entry, add it
		if ($null -eq $config.subscriptions.${name}.file) {
			$config.subscriptions.${name} | Add-Member -Name file -Value @{} -MemberType NoteProperty
		}
		$config.subscriptions.${name}.file = $file

		# Compare file hashes, redownload if they don't match
		if (Test-Path zips/$file) {
			$mod_md5 = Get-FileHash zips/$file -Algorithm MD5 | Select-Object -ExpandProperty Hash
			if ($mod_md5 -ne $data.filehash.md5) {
				$update = $true # already up to date
				Write-Output "    File mismatch"
			}
		}

		if (-not(Test-Path zips/$file) -or $update) {
			Write-Output "    Downloading $file..."
			$url = $data.download.binary_url

			# Suppress progress bar to vastly improve download speed
			# https://stackoverflow.com/questions/28682642/powershell-why-is-using-invoke-webrequest-much-slower-than-a-browser-download
			$ProgressPreference = 'SilentlyContinue'

			Invoke-WebRequest -UseBasicParsing -URI $url -OutFile zips/$file
		}
		else {
			Write-Output "    Skipped download of $file (already exists and up to date)."
		}

		if ($unpack) {
			$zip = [System.IO.Compression.ZipFile]::OpenRead("zips/$file")
			$fileCount = $zip.Entries.Count
			$fileStr = if ($fileCount -gt 1) { "files" } else { "file" }
			Write-Output "    Extracting $fileCount $fileStr..."
			Write-Output ""
			foreach ($entry in $zip.Entries) {
				$dst = [io.path]::combine($destination, $entry.FullName)

				# If the file already exists, check if the hashes match
				if ((Test-Path $dst)) {
					# Generate md5 hash of the destination file
					$dst_md5 = Get-FileHash $dst -Algorithm MD5 | Select-Object -ExpandProperty Hash

					# Generate md5 hash of the file within the zip
					$stream = $entry.Open()
					$md5 = [System.Security.Cryptography.MD5]::Create()
					$hash = $md5.ComputeHash($stream)
					$zip_md5 = [BitConverter]::ToString($hash) -replace '-', ''
					$stream.Close()

					# If the hashes don't match, extract the file
					if ($dst_md5 -eq $zip_md5) {
						Write-Output $("      Skipped extract of {0} (files match)" -f @($entry.FullName))
						continue
					}
				}

				Write-Output $("      Extract ==> {0}" -f @($entry.FullName))
				if (Test-Path $dst) {
					Remove-Item $dst
				}
				# Use 7zip to extract for better performance and supporting Deflate64
				& 7z x -y -o"$destination" "zips/$file" $entry.FullName > $null
			}
			$zip.Dispose()
		}
	}
}

Write-Output ""
Write-Output "Checking for removed subscriptions..."
# Remove any files that are no longer subscribed to
$files = Get-ChildItem zips
foreach ($file in $files) {
	$found = $false
	foreach ($sub in $sublist.data) {
		if ($sub.modfile.filename -eq $file) {
			$found = $true
			break
		}
	}
	if (-not($found)) {
		Write-Output "  Removing $file"
		# Find the subscription that contains this file and remove it
		foreach ($sub in $config.subscriptions.psobject.properties) {
			if ($sub.value.file -eq $file) {
				Write-Output "    Removing config entry for $file"
				$config.subscriptions.psobject.properties.remove($sub.name)
			}
		}
		Remove-Item zips/$file
	}
}

# Write updates to the config file
$config | ConvertTo-Json | Set-Content config.json

Write-Output '' ''
Write-Output "All subscriptions downloaded and up to date."
Write-Output '' ''
Pause
