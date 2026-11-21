#!/usr/bin/env bash
# Exportiert Kurven eines MC-Laufs als Text (läuft auf dem Server, Aufruf über run_remote.sh).
# Args: <MC-Nummer> <Iter von> <Iter bis> <VG1-Werte ...>
#   z. B.: bash run_remote.sh remote_waves.sh 18 1 10 1 1.5
# Ergebnis: ~/exports/MC<n>_waves/vg<VG1>_i<iter>.txt (Spalten: t vg1 vout vcin va vg2)
# Ordner der Nominal Corner (ohne mc-Section) werden übersprungen.
set -uo pipefail
n=$1; i0=$2; i1=$3; shift 3; vgs="$*"
R=$HOME/simulation/SNN_Neuron/neuron_tb/adexl/results/data/MonteCarlo.$n
OUT=$HOME/exports/MC${n}_waves
TMP=$(mktemp -d /tmp/aljmal_waves.XXXX)
mkdir -p "$OUT"

# Corner-Ordner zu den gewünschten VG1-Werten suchen
dirs=""
for c in $(ls "$R" | grep -E '^[0-9]+$' | sort -n); do
  d="$R/$c/SNN_Neuron:neuron_tb:1/groupRunDataDir"
  [ -d "$d/psf/mc1_separate" ] || continue
  grep -q 'section=mc' "$d/netlist/input.scs" 2>/dev/null || continue
  v=$(grep -o 'VG1=[0-9.e-]*' "$d/netlist/input.scs" | head -1 | cut -d= -f2)
  for w in $vgs; do
    if awk -v a="$v" -v b="$w" 'BEGIN{exit !(a+0 == b+0)}'; then dirs="$dirs $c:$w"; fi
  done
done
echo "Gefunden (Ordner:VG1):$dirs"
[ -n "$dirs" ] || { rm -rf "$TMP"; exit 1; }

{
  echo "base = \"$R\""
  for cv in $dirs; do
    c=${cv%%:*}; w=${cv##*:}
    cat <<EOF
for(i $i0 $i1
  dir = sprintf(nil "%s/$c/SNN_Neuron:neuron_tb:1/groupRunDataDir/psf/mc1_separate/%03d" base i)
  when(isDir(dir)
    openResults(dir)
    selectResult('tran)
    p = outfile(sprintf(nil "$OUT/vg${w}_i%02d.txt" i) "w")
    ocnPrint(VT("/vg1") VT("/vout") VT("/neuron0/vcin") VT("/neuron0/va") VT("/neuron0/vg2")
             ?output p ?numberNotation 'scientific ?precision 6 ?from 0 ?to 0.005 ?step 1e-6)
    close(p)
  )
)
EOF
  done
  echo "exit()"
} > "$TMP/waves.ocn"

cd "$TMP"
set +u   # Cadence-Setup-Skripte nutzen ungesetzte Variablen
source ~/cadence/environment.sh >/dev/null 2>&1
set -u
start=$(date +%s)
ocean -nograph -log "$TMP/CDS.log" -restore "$TMP/waves.ocn" < /dev/null > "$TMP/ocean.out" 2>&1 || echo "ocean exit $?"
echo "Dauer: $(( $(date +%s) - start )) s"
grep -iE "error|license" "$TMP/ocean.out" "$TMP/CDS.log" 2>/dev/null | head -10
ls "$OUT" | wc -l; du -sh "$OUT"
f=$(ls "$OUT"/*.txt 2>/dev/null | head -1); [ -n "$f" ] && { echo "== $f"; sed -n '1,6p' "$f"; wc -l "$f"; }
rm -rf "$TMP"
