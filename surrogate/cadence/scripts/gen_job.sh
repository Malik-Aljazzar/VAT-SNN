#!/usr/bin/env bash
# One generation job (runs on the server, called by gen_run.sh via xargs):
# one Spectre call = one signal × one chip group (MC iterations firstrun … firstrun+numruns−1) at fixed (VDD, T).
# Args: <Name> <group> <firstrun> <numruns> <VDD> <T> <seed> <signal relative to ~/stimuli/<Name>>   (variation always process + mismatch)
# Result: ~/exports/<Name>/sims/g<group>/<signal>_i<chip>.csv (t, vg1, vout); θ: ~/exports/<Name>/theta/g<group>_<signal>_*

# Treat unset variables as errors (-u), report errors inside pipes
set -uo pipefail
# Put the 8 arguments (dataset name + one line of the job file) into variables with readable names
name=$1; g=$2; first=$3; runs=$4; vdd=$5; temp=$6; seed=$7; stim=$8
# S = path of the signal file on the server; b = its name without folder and without the .pwl ending (e.g. A_003)
S=$HOME/stimuli/$name/$stim; b=$(basename "$stim" .pwl)
# OUT = folder for the traces of this group, TH = folder for the θ values, ST = status file of the run
OUT=$HOME/exports/$name/sims/g$g; TH=$HOME/exports/$name/theta; ST=$HOME/simruns/$name/status.txt
# Netlist of an earlier ADE run (MonteCarlo.20); we take the circuit of the neuron from it
src=$HOME/simulation/SNN_Neuron/neuron_tb/adexl/results/data/MonteCarlo.20/2/SNN_Neuron:neuron_tb:1/groupRunDataDir/netlist/input.scs
# If the signal file is missing, write that to the status file and end the job
[ -f "$S" ] || { echo "$(date +%T) g$g $b FEHLT" >> "$ST"; exit 1; }
# Create the output folders (end the job on error)
mkdir -p "$OUT" "$TH" || exit 1
# Create an empty working folder under /tmp (XXXX is replaced randomly) so that parallel jobs do not interfere
W=$(mktemp -d /tmp/aljmal_gen.XXXX) || exit 1
# Change into the working folder
cd "$W" || exit 1
# Take lines 7–55 of the ADE netlist (the circuit) and replace "VDD=… VG1=…" by "VDD=<VDD of this group>"
# (sed -E "s/old/new/"); the result is the new netlist net.scs
sed -n '7,55p' "$src" | sed -E "s/VDD=[0-9.]+ VG1=[0-9.]+/VDD=$vdd/" > net.scs
# Append the following lines up to EOF to net.scs:
#   V1:               input source at vg1, follows the signal file (pwl = piecewise linear)
#   vdd:              supply voltage VDD
#   simulatorOptions: accuracy of the simulator and the temperature of this group
cat >> net.scs <<EOF
V1 (vg1 0) vsource type=pwl file="$S"
vdd (net1 0) vsource dc=VDD type=dc
simulatorOptions options reltol=1e-3 vabstol=1e-6 iabstol=1e-12 temp=$temp tnom=27 gmin=1e-12
EOF
# Likewise append the Monte Carlo analysis (\\ at the end of a line = the statement continues on the next line):
#   numruns chips from chip firstrun, fixed seed, variation process + mismatch (variations=all), lds sampling;
#   write the θ values of every chip to processData / mismatchData, results of each chip into its own folder.
#   Inside, for every chip a transient simulation over 5 ms, values on a 1 µs grid.
cat >> net.scs <<EOF
mc1 montecarlo numruns=$runs firstrun=$first seed=$seed variations=all sampling=lds donominal=no \\
    saveprocessparams=yes processscalarfile="processData" processparamfile="processParam" \\
    savemismatchparams=yes dumpdependency=mismatch dependencyscalarfile="mismatchData" \\
    dependencyparamfile="mismatchParam" savedatainseparatedir=yes savefamilyplots=yes wfseparation=yes {
  tran tran stop=5m strobeperiod=1u maxiters=5
}
EOF
# Save only the nodes vg1 and vout
echo "save vg1 vout" >> net.scs
# Load the Cadence environment so that the command spectre is found (discard output; -u briefly off because the file uses unset variables)
set +u; source "$HOME/cadence/environment.sh" >/dev/null 2>&1; set -u
# Remember the start time in seconds (for the run time)
s=$(date +%s)
# Start Spectre: netlist net.scs, fast mode (+aps), results as text (psfascii) in the folder raw, messages to spectre.log; rc = return code (0 = ok)
spectre net.scs +aps -format psfascii -raw raw +escchars > spectre.log 2>&1; rc=$?
# Path of the Python script that converts Spectre results to CSV
P=$HOME/simruns/_scripts/psf_to_csv.py
# For each folder Spectre created (one per chip):
for d in raw/mc1_separate/*/; do
  # i = chip number (= folder name); p = result file of the transient simulation in it
  i=$(basename "$d"); p=$(ls "$d"*tran.tran* 2>/dev/null | head -1)
  # if found: convert to a CSV with the columns t, vg1, vout, named <signal>_i<chip>.csv
  [ -n "$p" ] && python3 "$P" "$p" "$OUT/${b}_i${i}.csv" vg1 vout > /dev/null 2>&1
# end of the loop
done
# Keep the four θ files (process and mismatch values with their names), with group and signal in the file name
for t in processData processParam mismatchData mismatchParam; do cp "raw/$t" "$TH/g${g}_${b}_$t" 2>/dev/null; done
# If Spectre ended with an error (rc ≠ 0) …
if [ "$rc" -ne 0 ]; then
  # … keep log and netlist in ~/simruns/<Name>/failed/ so that the error can be looked at
  F=$HOME/simruns/$name/failed; mkdir -p "$F" && cp spectre.log "$F/g${g}_${b}.log" && cp net.scs "$F/g${g}_${b}.scs"
# end of the condition
fi
# Count how many CSV files were created for this signal (should equal the chips of the group)
n=$(ls "$OUT/${b}"_i*.csv 2>/dev/null | wc -l)
# Append a result line to the status file: time, group, signal, return code, number of CSV files, run time in seconds
echo "$(date +%T) g$g $b rc=$rc n=$n $(( $(date +%s) - s ))s" >> "$ST"
# Delete the working folder again
cd / && rm -rf "$W"
