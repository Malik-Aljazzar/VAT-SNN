# Uploads the scripts that run on the server (gen_job.sh, psf_to_csv.py from 03_Cadence/scripts) to ~/simruns/_scripts.
# Upload under a temporary name first, then rename: a job that is running keeps its old version.
# Called by simulate.ps1; on its own: .\utils\upload_server_scripts.ps1   (server: entry "i83compute3" in ~/.ssh/config)

# Stop at the first error …
$ErrorActionPreference = "Stop"
# … also when an external program (ssh, scp) ends with an error
$PSNativeCommandUseErrorActionPreference = $true
# Name of the server in ~/.ssh/config
$H = "i83compute3"
# Create the target folder on the server (-p: no error if it already exists); BatchMode: never ask for a password
ssh -o BatchMode=yes $H "mkdir -p ~/simruns/_scripts"
# Change into 03_Cadence/scripts (one level above this file), so that scp gets short relative paths
# (with "C:\…" it could take "C" for a server)
Push-Location (Split-Path $PSScriptRoot -Parent)
# try/finally: change back to the old folder at the end, even after an error
try {
    # For each of the two scripts needed on the server:
    foreach ($f in "psf_to_csv.py", "gen_job.sh") {
        # upload it via scp (copy over ssh) under the hidden name .<file>.neu (-q: no progress output)
        scp -q -o BatchMode=yes $f "${H}:simruns/_scripts/.$f.neu"
        # rename it on the server to its real name (-f: overwrite an existing file)
        ssh -o BatchMode=yes $H "mv -f ~/simruns/_scripts/.$f.neu ~/simruns/_scripts/$f"
    # end of the loop
    }
# in any case (also after an error):
} finally {
    # change back to the folder from before
    Pop-Location
# end of try/finally
}
# Short confirmation
Write-Output "Server-Skripte hochgeladen: psf_to_csv.py, gen_job.sh"
