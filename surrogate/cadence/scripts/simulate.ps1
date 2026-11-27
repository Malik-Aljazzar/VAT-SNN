# Starts a simulation run on the server – the one script to run for a stage:
#   1. uploads the server scripts (gen_job.sh, psf_to_csv.py), 2. uploads the signals and job files of the dataset,
#   3. starts all jobs of the job file on the server (in the background, they keep running without this window).
# Usage (PowerShell, in this folder): .\simulate.ps1 <Name> <job file> [<parallel>]
#   stage 1: .\simulate.ps1 <Name> jobs_base_stimuli.txt 8   ·   stage 2: .\simulate.ps1 <Name> jobs_cascade.txt 8
# Afterwards: progress with  ssh i83compute3 "tail ~/simruns/<Name>/status.txt"  and at "DONE" fetch with .\fetch_tar.ps1 <Name>

# Read the arguments: dataset name, job file (in 03_Cadence/stimuli/<Name>), Spectre processes at the same time (default 8)
param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)][string]$JobFile, [int]$Parallel = 8)
# Stop at the first error, also in the helper scripts
$ErrorActionPreference = "Stop"
# Folder with the helper scripts
$U = Join-Path $PSScriptRoot "utils"
# Local path of the job file
$jobs = Join-Path (Split-Path $PSScriptRoot -Parent) "stimuli\$Name\$JobFile"
# Stop before uploading anything if the job file does not exist
if (-not (Test-Path $jobs)) { throw "$jobs is missing" }
# 1. Upload the server scripts (every time, so that the server never runs an old version)
& (Join-Path $U "upload_server_scripts.ps1")
# 2. Upload the folder 03_Cadence/stimuli/<Name> (signals and job files)
& (Join-Path $U "upload_stimuli.ps1") $Name
# 3. Start all jobs of the job file on the server
& (Join-Path $U "start_run.ps1") $Name $JobFile $Parallel
# Remind how to follow the progress
Write-Output "Progress: .\status.ps1 $Name   or   ssh i83compute3 `"tail ~/simruns/$Name/status.txt`"   (at the end: DONE $JobFile)"
