#!/usr/bin/env bash
# A aus: Bias-Zeile per Pulsquelle bei 10 µs einschalten (sonst startet Spectre im instabilen DC-Punkt).
# Aufruf nach kaskade_waves.sh (überschreibt dessen zwei Fälle „A aus“): bash run_remote.sh kaskade_waves_Aaus.sh
set -uo pipefail
src=$HOME/simulation/SNN_Neuron/cascade_tb/adexl/results/data/Interactive.25/1/SNN_Neuron:neuron_tb:1/netlist/input.scs
W=$HOME/simruns/kaskade_plot; OUT=$HOME/exports/kaskade_plot
cd "$W" || exit 1
set +u; source ~/cadence/environment.sh >/dev/null 2>&1; set -u
run() {
  n=$1; rin=$2
  rm -rf "$n"; mkdir -p "$n" && cd "$n" || return
  sed -n '1,58p' "$src" | sed -E "s/Rb=[0-9.]+M Rin=[0-9.]+M VDD=[0-9.]+ VG1=[0-9.]+/Rb=10M Rin=$rin VDD=1.5 VG1=0/" > net.scs
  cat >> net.scs <<EON
Rin (voutA x) resistor r=Rin
Rb (x bias) resistor r=Rb
Vb (bias 0) vsource dc=0 type=pulse delay=10u val0=0 val1=VDD period=2 rise=1u fall=1u width=1
simulatorOptions options reltol=1e-3 vabstol=1e-6 iabstol=1e-12 temp=27 tnom=27 gmin=1e-12
tran tran stop=2m strobeperiod=1u maxiters=5
save vg1 voutA x voutB neuron1.vcin
EON
  spectre net.scs +aps -format psfascii -raw raw +escchars > spectre.log 2>&1 || { echo "$n: Spectre-Fehler"; grep -A3 ERROR spectre.log | head -6; }
  python3 ~/simruns/_scripts/psf_to_csv.py raw/tran.tran.tran "$OUT/$n.csv" vg1 voutA x voutB neuron1.vcin
}
run vdd_10M_Aaus 10M &
run vdd_40M_Aaus 40M &
wait
