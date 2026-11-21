#!/usr/bin/env bash
# Kaskadentest erneut simulieren, diesmal mit Verläufen (läuft auf dem Server).
# Aufruf (aus WSL): bash run_remote.sh kaskade_waves.sh, danach Ordner ~/exports/kaskade_plot holen (fetch_tar.sh kaskade_plot)
# Netzliste: cascade_tb aus ADE (Interactive.25), Rin/Rb/VG1 werden ersetzt. Fälle „A aus“ mit Bias-Rampe: kaskade_waves_Aaus.sh
# Fälle: <Name> <Rb-Knoten: 0=GND, net1=VDD> <Rin> <VG1 von A>
set -uo pipefail
src=$HOME/simulation/SNN_Neuron/cascade_tb/adexl/results/data/Interactive.25/1/SNN_Neuron:neuron_tb:1/netlist/input.scs
W=$HOME/simruns/kaskade_plot; OUT=$HOME/exports/kaskade_plot
rm -rf "$W" "$OUT"; mkdir -p "$W" "$OUT"; cd "$W" || exit 1
set +u; source ~/cadence/environment.sh >/dev/null 2>&1; set -u
run() {
  n=$1; rbnode=$2; rin=$3; vg=$4
  mkdir -p "$n" && cd "$n" || return
  sed -n '1,58p' "$src" | sed -E "s/Rb=[0-9.]+M Rin=[0-9.]+M VDD=[0-9.]+ VG1=[0-9.]+/Rb=10M Rin=$rin VDD=1.5 VG1=$vg/" > net.scs
  cat >> net.scs <<EON
Rin (voutA x) resistor r=Rin
Rb (x $rbnode) resistor r=Rb
simulatorOptions options reltol=1e-3 vabstol=1e-6 iabstol=1e-12 temp=27 tnom=27 gmin=1e-12
tran tran stop=2m strobeperiod=1u maxiters=5
save vg1 voutA x voutB neuron1.vcin
EON
  spectre net.scs +aps -format psfascii -raw raw +escchars > spectre.log 2>&1 || { echo "$n: Spectre-Fehler"; grep -A3 ERROR spectre.log | head -6; }
  grep -m1 "^parameters" net.scs
  python3 ~/simruns/_scripts/psf_to_csv.py raw/tran.tran.tran "$OUT/$n.csv" vg1 voutA x voutB neuron1.vcin
}
run gnd_2M5   0    2.5M 1.2 &
run gnd_10M   0    10M  1.2 &
run vdd_2M5   net1 2.5M 1.2 &
run vdd_10M   net1 10M  1.2 &
run vdd_40M   net1 40M  1.2 &
run vdd_10M_Aaus net1 10M 0 &
run vdd_40M_Aaus net1 40M 0 &
wait
ls -la "$OUT"
