# Uploads a local stimulus folder (03_Cadence/stimuli/<Name>: signals, job files, csv files) to ~/stimuli/<Name> on the server.
# Called by simulate.ps1; on its own: .\utils\upload_stimuli.ps1 <Name>   (server: entry "i83compute3" in ~/.ssh/config)

# Read the argument: name of the dataset
param([Parameter(Mandatory)][string]$Name)
# Stop at the first error …
$ErrorActionPreference = "Stop"
# … also when an external program (ssh, scp) ends with an error
$PSNativeCommandUseErrorActionPreference = $true
# Name of the server in ~/.ssh/config
$H = "i83compute3"
# Local folder 03_Cadence/stimuli (two levels above this file: utils → scripts → 03_Cadence)
$stim = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "stimuli"
# Stop with an error message if the folder of this dataset does not exist
if (-not (Test-Path (Join-Path $stim $Name))) { throw "$stim\$Name fehlt" }
# Create the folder ~/stimuli on the server (-p: no error if it already exists); BatchMode: never ask for a password
ssh -o BatchMode=yes $H "mkdir -p ~/stimuli"
# Change into the local stimuli folder, so that scp gets a short relative path (with "C:\…" it could take "C" for a server)
Push-Location $stim
# try/finally: change back to the old folder at the end, even after an error
try {
    # Copy the whole folder (-r: including subfolders) to ~/stimuli/ via scp (-q: no progress output)
    scp -q -r -o BatchMode=yes $Name "${H}:stimuli/"
# in any case (also after an error):
} finally {
    # change back to the folder from before
    Pop-Location
# end of try/finally
}
# Count the signal files that are now on the server, as a check
$n = ssh -o BatchMode=yes $H "find ~/stimuli/$Name -name '*.pwl' | wc -l"
# and print the number
Write-Output "Signale hochgeladen: ~/stimuli/$Name ($n PWL-Dateien auf dem Server)"
