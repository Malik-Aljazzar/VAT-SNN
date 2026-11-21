# Starts all jobs of a job file on the server: sends gen_run.sh (03_Cadence/scripts) to a shell on the server, which
# starts gen_job.sh for every line of the job file in the background and returns at once.
# Called by simulate.ps1; on its own: .\utils\start_run.ps1 <Name> <job file> <parallel>   (server: entry "i83compute3" in ~/.ssh/config)

# Read the arguments: dataset name, job file (in ~/stimuli/<Name> on the server), Spectre processes at the same time
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$JobFile, [Parameter(Mandatory)][int]$Parallel)
# Stop at the first error …
$ErrorActionPreference = "Stop"
# … also when an external program (here ssh) ends with an error
$PSNativeCommandUseErrorActionPreference = $true
# Path of gen_run.sh (one level above this file)
$script = Join-Path (Split-Path $PSScriptRoot -Parent) "gen_run.sh"
# Read gen_run.sh as raw bytes, so that its Unix line endings reach the server unchanged
$bytes = [IO.File]::ReadAllBytes($script)
# Send the bytes to a shell on the server that reads its script from this input ("bash -s") and gets the
# arguments after "--"; BatchMode: never ask for a password, log in with the key
$bytes | ssh -o BatchMode=yes i83compute3 "bash -s -- $Name $JobFile $Parallel"
