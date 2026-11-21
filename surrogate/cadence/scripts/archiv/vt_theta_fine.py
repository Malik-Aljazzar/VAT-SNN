"""θ × V/T mit feinem Raster (Checkliste 15): ΔVth und k je Chip an allen V/T-Ecken.

Nutzung: python vt_theta_fine.py <freq.csv aus direct_mc.sh> [Referenz-Ecke, Standard V1.5_T27]
Schwelle je Chip/Ecke = Mitte zwischen letztem VG1 ohne und erstem mit Spikes; k = f_Ecke/f_Ref bei 1,15–1,25 V.
"""
import csv, sys, re
from collections import defaultdict
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

path = sys.argv[1]; ref = sys.argv[2] if len(sys.argv) > 2 else "V1.5_T27"
K_VG1 = (1.15, 1.2, 1.25)
data = defaultdict(lambda: defaultdict(dict))            # Ecke -> Chip -> VG1 -> freq
for r in csv.DictReader(open(path)):
    data[re.sub(r"_\d+$", "", r["Corner"])][int(r["mc_iteration"])][float(r["VG1"])] = float(r["freq"])

def th(d):
    v = sorted(d)
    lo = max((a for a in v if d[a] == 0 and a <= 1.1), default=np.nan)
    hi = min((a for a in v if d[a] > 0), default=np.nan)
    return (lo + hi) / 2 * 1000

chips = sorted(data[ref]); tr = np.array([th(data[ref][i]) for i in chips])
print(f"Referenz {ref}: Schwellen [mV] " + " ".join(f"{x:.0f}" for x in tr))
print(f"\n{'Ecke':10s} {'ΔVth μ':>7s} {'σ':>5s} {'Spanne':>13s} {'r(th_ref)':>9s} | {'k μ':>6s} {'σ %':>5s} {'r(th_ref)':>9s}")
for c in sorted(data):
    if c == ref:
        continue
    dv = np.array([th(data[c][i]) for i in chips]) - tr
    k = np.array([np.mean([data[c][i][v] / data[ref][i][v] for v in K_VG1]) for i in chips])
    print(f"{c:10s} {dv.mean():+7.1f} {dv.std(ddof=1):5.1f} {dv.min():+6.0f}…{dv.max():+4.0f} {np.corrcoef(tr, dv)[0, 1]:+9.2f} | "
          f"{k.mean():6.3f} {k.std(ddof=1) / k.mean() * 100:5.2f} {np.corrcoef(tr, k)[0, 1]:+9.2f}")
    print("           ΔVth je Chip: " + " ".join(f"{x:+.0f}" for x in dv))
