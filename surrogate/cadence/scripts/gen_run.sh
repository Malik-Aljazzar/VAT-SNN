#!/usr/bin/env bash
# Starts all jobs of a job file in the background, <parallel> Spectre processes at the same time (runs on the server).
# Args: <Name> <job file relative to ~/stimuli/<Name>> <parallel>
# Job line: <group> <firstrun> <numruns> <VDD> <T> <seed> <signal>   (→ gen_job.sh)
# Progress: ~/simruns/<Name>/status.txt (one line per job, at the end "FERTIG <job file>")

# Treat unset variables as errors (-u), report errors inside pipes; no -e, so that one error does not stop everything
set -uo pipefail
# $1 = name of the dataset, $2 = job file (lies in ~/stimuli/<Name>), $3 = jobs at the same time (default 8)
name=$1; jobs=$HOME/stimuli/$name/$2; par=${3:-8}
# Stop if the job file is missing ([ -f … ] = file exists?; || = run only if not)
[ -f "$jobs" ] || { echo "$jobs fehlt"; exit 1; }
# Create the folder for status file and log (stop on error)
mkdir -p "$HOME/simruns/$name" || exit 1
# Number of jobs = number of non-empty lines in the job file
n=$(grep -c . "$jobs")
# Append a start line with the time to the status file (>> = append instead of overwrite)
echo "$(date +%T) START $2 ($n Jobs, $par parallel)" >> "$HOME/simruns/$name/status.txt"
# The actual work (two lines, \ = line continues), detached from the terminal (nohup setsid) so that it keeps
# running when the connection ends: xargs reads the job file line by line (-L 1) and starts gen_job.sh for each
# line with the values of the line as arguments, at most <parallel> at the same time (-P). When all are done,
# "FERTIG <job file>" goes into the status file. Second line: all output to run.log, read nothing from the
# keyboard, & = start in the background.
nohup setsid bash -c "xargs -P $par -L 1 bash $HOME/simruns/_scripts/gen_job.sh $name < '$jobs'; echo \"\$(date +%T) FERTIG $2\" >> $HOME/simruns/$name/status.txt" \
  > "$HOME/simruns/$name/run.log" 2>&1 < /dev/null &
# Feedback; the script ends right away, the jobs keep running in the background
echo "gestartet: $n Jobs aus $2, $par parallel"
