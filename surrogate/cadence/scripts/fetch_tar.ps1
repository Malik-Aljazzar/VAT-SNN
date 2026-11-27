# Fetches a folder (or some of its files) from ~/exports compressed: tar on the server, scp, unpack locally, delete the archives.
# One archive instead of thousands of single files – therefore much faster than scp -r.
# Usage (PowerShell): .\fetch_tar.ps1 <Name> [<pattern>]   → 03_Cadence/exports/<Name>/ (existing files are updated)
#   <pattern>: only files whose name matches (find -name), e.g. '*D2_*' for the new cascade signals including θ
# Server, user and key: entry "i83compute3" in ~/.ssh/config

# Read the arguments: name of the folder in ~/exports and the pattern (empty if not given)
param([Parameter(Mandatory)][string]$Name, [string]$Pattern = "")
# Stop at the first error …
$ErrorActionPreference = "Stop"
# … also when an external program (ssh, scp, tar) ends with an error
$PSNativeCommandUseErrorActionPreference = $true
# Name of the server in ~/.ssh/config
$H = "i83compute3"
# Local target folder 03_Cadence/exports (next to the folder of this file)
$dst = Join-Path (Split-Path $PSScriptRoot -Parent) "exports"
# Was a pattern given (non-empty text)?
if ($Pattern) {
    # Yes: on the server, find all files in the folder whose name matches the pattern (find) and pack only these
    # into the compressed archive <Name>.tgz (tar czf; "--null -T -" reads the file list that find delivers)
    ssh -o BatchMode=yes $H "cd ~/exports && find '$Name' -type f -name '$Pattern' -print0 | tar czf '$Name.tgz' --null -T -"
# No:
} else {
    # pack the whole folder into the archive <Name>.tgz
    ssh -o BatchMode=yes $H "cd ~/exports && tar czf '$Name.tgz' '$Name'"
# end of the case distinction
}
# Change into the local target folder, so that scp gets short relative paths (with "C:\…" it could take "C" for a server)
Push-Location $dst
# try/finally: change back to the old folder at the end, even after an error
try {
    # Fetch the archive from the server via scp (-q: no progress output)
    scp -q -o BatchMode=yes "${H}:exports/$Name.tgz" "$Name.tgz"
    # Delete the archive on the server again
    ssh -o BatchMode=yes $H "rm -f ~/exports/'$Name.tgz'"
    # Unpack the archive with the tar built into Windows (x = extract, z = compressed with gzip, f = from this file)
    tar xzf "$Name.tgz"
    # Delete the local archive
    Remove-Item "$Name.tgz"
# in any case (also after an error):
} finally {
    # change back to the folder from before
    Pop-Location
# end of try/finally
}
# Count the CSV files that are now in the local folder (-Recurse: including subfolders)
$n = (Get-ChildItem (Join-Path $dst $Name) -Recurse -Filter *.csv -File).Count
# and print the number
Write-Output "${Name}: $n CSV files locally"
