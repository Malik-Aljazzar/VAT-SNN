# Fetches a folder (or some of its files) from ~/exports compressed: tar on the server, sftp, unpack locally, delete the archives.
# One archive instead of thousands of single files – therefore much faster than scp -r.
# If the connection drops, the download continues where it stopped (sftp reget), up to $MaxAttempts times.
# If a run was aborted during the download, the next run with the same name continues it instead of packing again.
# Usage (PowerShell): .\fetch_tar.ps1 <Name> [<pattern>]   → surrogate/cadence/exports/<Name>/ (existing files are updated)
#   <pattern>: only files whose name matches (find -name), e.g. '*D2_*' for the new cascade signals including θ
# Server, user and key: entry "i83compute3" in ~/.ssh/config

# Read the arguments: name of the folder in ~/exports and the pattern (empty if not given)
param([Parameter(Mandatory)][string]$Name, [string]$Pattern = "")
# Stop at the first error …
$ErrorActionPreference = "Stop"
# … also when an external program (ssh, sftp, tar) ends with an error
$PSNativeCommandUseErrorActionPreference = $true
# Name of the server in ~/.ssh/config
$H = "i83compute3"
# Number of download attempts before the script gives up (every attempt continues where the one before stopped)
$MaxAttempts = 40
# Local target folder surrogate/cadence/exports (next to the folder of this file)
$dst = Join-Path (Split-Path $PSScriptRoot -Parent) "exports"
# Full path of the local archive (after an aborted run a partial one may already be there)
$archive = Join-Path $dst "$Name.tgz"

# Size of the local archive in bytes, 0 if there is none
function LocalSize {
    # Is there a local archive?
    if (Test-Path $archive) {
        # Yes: its size
        return (Get-Item $archive).Length
    # end of the case distinction
    }
    # No: 0
    return 0
}
# Size of the archive on the server in bytes, 0 if there is none
function RemoteSize {
    # stat prints the size; if the archive is missing, stat fails and "|| echo 0" prints 0 instead (so ssh does not fail)
    return [long](ssh -o BatchMode=yes $H "stat -c %s ~/exports/'$Name.tgz' 2>/dev/null || echo 0")
}

# Size of the archive on the server (0 if there is none)
$remoteSize = RemoteSize
# Is there an archive on the server and a partial local one that is not larger (left over from an aborted download)?
if ($remoteSize -gt 0 -and (LocalSize) -gt 0 -and (LocalSize) -le $remoteSize) {
    # Yes: do not pack again, the download continues below
    Write-Output "Archive from an aborted run found ($(LocalSize) of $remoteSize bytes here), continuing the download"
# No:
} else {
    # Is there an old local archive (it would not match the new one)?
    if (Test-Path $archive) {
        # Yes: delete it, otherwise reget would append the new archive to it
        Remove-Item $archive
    # end of the case distinction
    }
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
    # Size of the new archive on the server
    $remoteSize = RemoteSize
# end of the case distinction
}
# Change into the local target folder, so that sftp gets short relative paths (with "C:\…" it could take "C" for a server)
Push-Location $dst
# try/finally: change back to the old folder at the end, even after an error
try {
    # Number of download attempts so far
    $attempt = 0
    # Repeat until the local archive is as large as the one on the server
    while ((LocalSize) -lt $remoteSize) {
        # One more attempt
        $attempt++
        # Too many attempts?
        if ($attempt -gt $MaxAttempts) {
            # Yes: give up; the partial archive stays, so a new run continues from here
            throw "Download incomplete after $MaxAttempts attempts ($(LocalSize) of $remoteSize bytes). Run the script again to continue."
        # end of the case distinction
        }
        # try/catch: a dropped connection should not end the script, only this attempt
        try {
            # Fetch the archive via sftp: reget continues a partial local file (starts from 0 if there is none),
            # -b - reads the command from the pipe, -q hides the progress output,
            # ServerAlive…: ask the server every 15 s whether it is still there and give up after 4 missing answers,
            # Out-Null: hide the echo of the command ("sftp> reget …"), error messages still appear
            "reget exports/$Name.tgz $Name.tgz" | sftp -q -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -b - $H | Out-Null
        # The connection dropped (sftp ended with an error):
        } catch {
            # say how far the download got
            Write-Output "Connection lost at $(LocalSize) of $remoteSize bytes (attempt $attempt of $MaxAttempts), next attempt in 15 s"
            # wait a little before the next attempt
            Start-Sleep -Seconds 15
        # end of try/catch
        }
    # end of the loop
    }
    # Delete the archive on the server again (only now, when the local one is complete)
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
