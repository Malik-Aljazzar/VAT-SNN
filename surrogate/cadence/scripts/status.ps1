# Shows the progress of the current run of a dataset on the server, every 5 seconds one line in the console.
# Stops by itself when the run is done (line "FERTIG" in the status file), otherwise with Ctrl+C (the run keeps going).
# Usage (PowerShell, in this folder): .\status.ps1 <Name> [<seconds>]   (server: entry "i83compute3" in ~/.ssh/config)

# Read the arguments: dataset name and the waiting time between two lines (default 5 s)
param([Parameter(Mandatory)][string]$Name, [int]$Seconds = 5)
# Name of the server in ~/.ssh/config
$H = "i83compute3"
# Command for the server: print the status file of the dataset, then the number of running Spectre processes of our user
# (single quotes: PowerShell leaves $(…) alone, the shell on the server evaluates it)
$cmd = 'cat ~/simruns/' + $Name + '/status.txt 2>/dev/null; echo "SPECTRE $(pgrep -u aljmal00 -c spectre)"'
# Wait-Rest: wait until $Seconds have passed since $t0, so that a line comes every $Seconds whatever ssh takes
function Wait-Rest($t0) { Start-Sleep -Milliseconds ([math]::Max(0, $Seconds * 1000 - ((Get-Date) - $t0).TotalMilliseconds)) }
# Repeat until the run is done (break below) or Ctrl+C is pressed
while ($true) {
    # Remember when this round started
    $t0 = Get-Date
    # Current time for the start of the line
    $now = Get-Date -Format HH:mm:ss
    # Run the command on the server (BatchMode: never ask for a password); @(…) always gives a list of lines
    $lines = @(ssh -o BatchMode=yes $H $cmd)
    # If the connection failed: say so, wait and try again
    if ($LASTEXITCODE -ne 0) { Write-Output "$now  keine Verbindung zum Server, neuer Versuch …"; Wait-Rest $t0; continue }
    # Number of running Spectre processes (last line "SPECTRE <n>")
    $spectre = ($lines[-1] -replace "SPECTRE ", "")
    # Line number of the last START line: the current run (earlier runs of the same dataset stand above it)
    $start = ($lines | Select-String " START " | Select-Object -Last 1).LineNumber
    # No START line yet: say so, wait and look again
    if (-not $start) { Write-Output "$now  noch kein Lauf für $Name gestartet"; Wait-Rest $t0; continue }
    # Lines of the current run: from the START line on, without the last line (Spectre count); @(…) keeps it a list
    $run = @($lines[($start - 1)..($lines.Count - 2)])
    # The START line looks like "14:34:28 START jobs_base_stimuli.txt (1200 Jobs, 8 parallel)"
    $head = $run[0]
    # job file = 3rd word of the START line
    $file = ($head -split " ")[2]
    # total number of jobs = the number in front of "Jobs"
    $total = [int][regex]::Match($head, "\((\d+) Jobs").Groups[1].Value
    # finished jobs = lines with a return code ("rc=…") or with a missing signal file ("FEHLT")
    $done = @($run | Where-Object { $_ -match " rc=| FEHLT$" })
    # failed jobs = Spectre error (rc ≠ 0), no CSV written (n=0) or signal file missing
    $errors = @($run | Where-Object { $_ -match " rc=[1-9]| n=0 | FEHLT$" })
    # share of finished jobs in percent (0 if the total is unknown)
    $pct = if ($total) { [math]::Round(100 * $done.Count / $total) } else { 0 }
    # last finished job, e.g. "14:34:33 g0 B_000 rc=0 n=10 5s" (empty if none yet)
    $last = if ($done.Count) { $done[-1] } else { "–" }
    # Print one status line
    Write-Output "$now  ${file}: $($done.Count)/$total Jobs fertig ($pct %), Fehler $($errors.Count), Spectre-Prozesse $spectre  ·  zuletzt: $last"
    # Is the run done (a line with "FERTIG")?
    if ($run -match " FERTIG ") {
        # list every failed job
        foreach ($e in $errors) { Write-Output "  Fehler: $e" }
        # final message with the next step
        Write-Output "Lauf fertig. Ergebnisse holen: .\fetch_tar.ps1 $Name"
        # leave the loop
        break
    # end of the condition
    }
    # Wait for the rest of the $Seconds before the next line
    Wait-Rest $t0
# end of the loop
}
