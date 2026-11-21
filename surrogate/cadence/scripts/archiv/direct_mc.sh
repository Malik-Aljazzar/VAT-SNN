#!/usr/bin/env bash
# Monte Carlo direkt mit Spectre statt ADE XL: ein Spectre-Prozess pro (VDD, T), darin MC × VG1-Sweep.
# Läuft auf dem Server (Aufruf über run_remote.sh), startet die Prozesse im Hintergrund (nohup).
# Args: <Name> <Chips> <Seed> <VDD,VDD,..> <T,T,..> <VG1,VG1,..>
#   z. B.: bash run_remote.sh direct_mc.sh MC20s 10 2 1.35,1.5,1.65 10,27,35 0.8,0.802,...
# Ergebnis: ~/simruns/<Name>/<Corner>/result.csv, gesammelt in ~/exports/<Name>_freq.csv
# Fortschritt: ~/simruns/<Name>/status.txt
set -uo pipefail
name=$1; runs=$2; seed=$3; vdds=$4; temps=$5; vg1s=$6
base=$HOME/simruns/$name
src=$HOME/simulation/SNN_Neuron/neuron_tb/adexl/results/data/MonteCarlo.20/2/SNN_Neuron:neuron_tb:1/groupRunDataDir/netlist/input.scs
script_dir=$HOME/simruns/_scripts
[ -e "$base" ] && { echo "$base existiert schon – abgebrochen"; exit 1; }
mkdir -p "$base" "$script_dir" || exit 1
[ -f "$script_dir/psf_freq.py" ] || { echo "psf_freq.py fehlt in $script_dir"; exit 1; }
vgl=$(echo "$vg1s" | tr ',' ' ')

cat > "$base/runner.sh" <<EOF
#!/usr/bin/env bash
set +u; source \$HOME/cadence/environment.sh >/dev/null 2>&1
cd "$base" || exit 1
for v in $(echo "$vdds" | tr ',' ' '); do for t in $(echo "$temps" | tr ',' ' '); do
  c="V\${v}_T\${t}"
  (
    mkdir -p "\$c" && cd "\$c" || exit 1
    sed -n '7,58p' "$src" | sed -E "s/^parameters flg_global_she=-1 VDD=[0-9.]+ VG1=[0-9.]+/parameters flg_global_she=-1 VDD=\$v VG1=1/" > net.scs
    cat >> net.scs <<NET
simulatorOptions options reltol=1e-3 vabstol=1e-6 iabstol=1e-12 temp=\$t \\\\
    tnom=27 scalem=1.0 scale=1.0 gmin=1e-12 rforce=1 maxnotes=5 maxwarns=5 \\\\
    digits=5 cols=80 pivrel=1e-3
mc1 montecarlo numruns=$runs seed=$seed variations=all sampling=lds donominal=no \\\\
    saveprocessparams=yes processscalarfile="processData" processparamfile="processParam" \\\\
    savemismatchparams=yes dumpdependency=mismatch dependencyscalarfile="mismatchData" \\\\
    dependencyparamfile="mismatchParam" savedatainseparatedir=yes savefamilyplots=yes wfseparation=yes {
  swG sweep param=VG1 values=[$vgl] {
    tran tran stop=5m strobeperiod=1u skipstart=1m maxiters=5
  }
}
save vout
NET
    echo "\$c start \$(date +%T)" >> ../status.txt
    spectre net.scs +aps -format psfascii -raw raw +escchars > spectre.log 2>&1
    echo "\$c spectre exit \$? \$(date +%T)" >> ../status.txt
    python3 "$script_dir/psf_freq.py" raw "\$c" "\$v" "\$t" "$vg1s" result.csv >> ../status.txt 2>&1
    cp raw/processData raw/processParam raw/mismatchData raw/mismatchParam . 2>/dev/null
    rm -rf raw *.ahdlSimDB
  ) &
done; done
wait
{ head -1 \$(ls */result.csv | head -1); for f in */result.csv; do tail -n +2 "\$f"; done; } > \$HOME/exports/${name}_freq.csv
echo "FERTIG \$(date +%T)" >> status.txt
EOF
chmod +x "$base/runner.sh"
nohup setsid bash "$base/runner.sh" > "$base/runner.log" 2>&1 < /dev/null &
echo "gestartet: $base (PID $!)"
