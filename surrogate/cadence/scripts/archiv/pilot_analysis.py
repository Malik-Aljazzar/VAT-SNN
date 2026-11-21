"""Pilot MC14: Konsistenz (Punkt 5) und Schwellen-/Frequenzstreuung (Punkt 6)."""
import csv, sys, statistics as st
sys.stdout.reconfigure(encoding="utf-8")
from collections import defaultdict

freq_csv, theta_txt, params_txt = sys.argv[1:4]

# --- freq-Tabelle
rows = [r for r in csv.DictReader(open(freq_csv)) if r["Corner"] != "nom"]
data = defaultdict(dict)          # inst -> {vg1: freq}
bad = []
for r in rows:
    try:
        data[int(r["mc_iteration"])][float(r["VG1"])] = float(r["freq"])
    except ValueError:
        bad.append(r)
vgs = sorted({v for d in data.values() for v in d})
print(f"Instanzen: {len(data)}, VG1-Werte: {len(vgs)}, Zeilen ohne Zahl: {len(bad)}")
print("VG1-Raster:", " ".join(f"{v:g}" for v in vgs))
missing = [(i, v) for i in data for v in vgs if v not in data[i]]
print("Fehlende Kombinationen:", len(missing))

# --- Monotonie: feuert ein Exemplar bei VG1 und bei einem höheren VG1 nicht mehr?
nonmono = [i for i, d in data.items()
           if any(d[a] > 0 and d[b] == 0 for a in vgs for b in vgs if b > a)]
print("Nicht monoton (feuert, dann bei höherem VG1 nicht mehr):", nonmono or "keine")

# --- Schwelle je Instanz (Intervall letztes 0 / erstes > 0)
th = {}
for i, d in sorted(data.items()):
    lo = max((v for v in vgs if d[v] == 0), default=None)
    hi = min((v for v in vgs if d[v] > 0), default=None)
    th[i] = (lo, hi)
mids = [(lo + hi) / 2 for lo, hi in th.values() if lo is not None and hi is not None]
print("\nSchwelle je Instanz [V] (letztes 0 .. erstes > 0):")
print("  " + "  ".join(f"#{i}:{lo:.2f}-{hi:.2f}" for i, (lo, hi) in th.items()))
print(f"μ_th = {st.mean(mids)*1000:.1f} mV, σ_th = {st.stdev(mids)*1000:.1f} mV "
      f"(Mitte der Intervalle, Raster 10 mV), Spanne {min(mids)*1000:.0f}–{max(mids)*1000:.0f} mV")
onset = [data[i][hi] for i, (lo, hi) in th.items()]
print(f"f beim ersten Feuern: {min(onset)/1e3:.2f}–{max(onset)/1e3:.2f} kHz")

# --- Frequenzstreuung bei festen VG1
print("\nFrequenz über Instanzen:")
for v in (1.0, 1.2, 1.5):
    f = [d[v] for d in data.values() if d[v] > 0]
    print(f"  VG1 = {v:.1f} V: μ = {st.mean(f)/1e3:.3f} kHz, σ/μ = {st.stdev(f)/st.mean(f)*100:.2f} % (n = {len(f)})")

# --- θ einlesen und Korrelation mit der Schwelle
names = []
group = None
for line in open(params_txt):
    t = line.strip()
    if not t:
        continue
    if t.startswith("mis_"):
        group = t
    else:
        names.append(f"{group.replace('mis_', '').replace('mm_', '')}:{t.replace('neuron0.', '')}")
theta, cur = {}, None
for line in open(theta_txt):
    t = line.strip()
    if t.startswith("#"):
        cur = int(t[1:])
    elif t:
        theta[cur] = [float(x) for x in t.split()]
print(f"\nθ: {len(theta)} Instanzen × {len(next(iter(theta.values())))} Werte, Namen: {len(names)}")

def corr(x, y):
    mx, my = st.mean(x), st.mean(y)
    sx = sum((a - mx) ** 2 for a in x) ** .5
    sy = sum((b - my) ** 2 for b in y) ** .5
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)

ids = sorted(th)
y = [(th[i][0] + th[i][1]) / 2 for i in ids]
cs = sorted(((corr([theta[i][k] for i in ids], y), names[k]) for k in range(len(names))),
            key=lambda c: -abs(c[0]))
print("Stärkste Korrelationen θ ↔ Schwelle (n = 20):")
for c, n in cs[:5]:
    print(f"  {n:28s} r = {c:+.2f}")
