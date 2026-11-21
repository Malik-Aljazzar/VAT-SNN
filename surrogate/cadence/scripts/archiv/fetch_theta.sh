#!/usr/bin/env bash
# Holt θ (Mismatch- und/oder Process-Werte) eines Monte-Carlo-Laufs vom Server.
# Nutzung: bash fetch_theta.sh <MonteCarlo-Nummer>
# Mismatch: MC<n>_theta.txt + MC<n>_theta_params.txt
# Process:  MC<n>_theta_process.txt + MC<n>_theta_process_params.txt
set -euo pipefail
n=$1
H=aljmal00@i83compute3.dcn.itec.kit.edu
dst=/mnt/c/Users/malik/Programming/05_KIT/05_BA/03_Cadence/exports
# Ordner mit nicht-leerer processData bevorzugen: Ist die Nominal Corner aktiv, enthält deren
# Ordner (ohne Process) falsche θ – die Mismatch-Werte dort gehören nicht zu den echten Chips.
src=$(ssh -o BatchMode=yes "$H" "d=\$(ls -d ~/simulation/SNN_Neuron/neuron_tb/adexl/results/data/MonteCarlo.$n/*/SNN_Neuron:neuron_tb:1/groupRunDataDir/monteCarlo); for x in \$d; do [ -s \$x/processData ] && { echo \$x; exit; }; done; echo \"\$d\" | head -1" 2>/dev/null)
echo "Quelle: $src"
[ -n "$src" ] || { echo "Kein monteCarlo-Ordner gefunden" >&2; exit 1; }
files=$(ssh -o BatchMode=yes "$H" "ls $src" 2>/dev/null)
get() { scp -q -o BatchMode=yes "$H:$src/$1" "$dst/$2" 2>/dev/null && echo "$1 -> $2"; }
if echo "$files" | grep -qx compactmismatchdata; then
  get compactmismatchdata  "MC${n}_theta.txt"
  get compactmismatchparam "MC${n}_theta_params.txt"
fi
if echo "$files" | grep -qx processData; then
  get processData  "MC${n}_theta_process.txt"
  get processParam "MC${n}_theta_process_params.txt"
fi
