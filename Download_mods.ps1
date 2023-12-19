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
	Write-Output "Requesting info about subscription $subname..."
	[string]$modid = $sub.id
	$mod_json = Invoke-WebRequest -UseBasicParsing -URI https://api.mod.io/v1/games/3791/mods/${modid}/files -Method GET -Headers @{"Authorization" = "Bearer ${token}"; "Accept" = "application/json" }
	$mod = ConvertFrom-Json $mod_json.Content

	# get latest version in remaining files and keep only files matching that version
	$mod.data = @($mod.data)
	$lastver = ($mod.data | Select-Object -ExpandProperty version | Measure-Object -Maximum).Maximum
	$mod.data = $mod.data | Where-Object { $_.version -ge $lastver }
	$mod.data = @($mod.data)
	Write-Output "Latest version: $lastver"

	# Write data about this sub to config
	$name = $sub.name_id

	$update = $true
	if ($null -eq $config.${name}) {
		$config | Add-Member -Name $name -Value @{} -MemberType NoteProperty
		$config.${name}.date_updated = $sub.date_updated
	}
	elseif ($sub.date_updated -le $config.${name}.date_updated) {
		$update = $false #already up to date
		Write-Output "$subname seems to be up to date - checking for missing files..."
	}

	$datalen = $mod.data.length
	[string]$datalen_str = $datalen
	Write-Output "$subname contains $datalen_str file(s)."

	for ($j = 0; $j -lt $datalen; $j++) {
		$data = $mod.data[$j]
		$file = $data.filename
		if (-not(Test-Path zips/$file) -or $update) {
			Write-Output "  Downloading $file..."
			$url = $data.download.binary_url

			# Suppress progress bar to vastly improve download speed
			# https://stackoverflow.com/questions/28682642/powershell-why-is-using-invoke-webrequest-much-slower-than-a-browser-download
			$ProgressPreference = 'SilentlyContinue'

			Invoke-WebRequest -UseBasicParsing -URI $url -OutFile zips/$file
			if ($unpack) {
				Write-Output "  Unpacking $file..."
				Expand-Archive zips/$file -DestinationPath $destination -Force
			}
		}
		else {
			Write-Output "  Skipped $file (already exists and up to date)."
		}
	}
}

# Write updates to the config file
$config | ConvertTo-Json | Set-Content config.json

Write-Output '' '' '' '' '' '' ''
Write-Output "This seems to be everything :)"
Pause
