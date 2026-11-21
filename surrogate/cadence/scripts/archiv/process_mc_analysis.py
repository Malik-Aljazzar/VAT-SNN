"""Process-MC auswerten (Checkliste Punkt 10).

Nutzung: python process_mc_analysis.py <freq.csv> <theta_process.txt> <theta_process_params.txt>
freq.csv: ADE-XL-Export (Detail-Transpose), theta_*: per fetch_theta.sh geholt.
"""
import csv, sys, statistics as st
from collections import defaultdict
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

freq_csv, theta_txt, params_txt = sys.argv[1:4]
# Process-Parameter mit σ ≠ 0 im PDK (Plan 3.1); die übrigen Spalten sind wirkungslos
RELEVANT = ["norm_vfbo", "norm_vfbl", "norm_uo", "norm_xcoro", "norm_xcorl", "norm_lovo",
            "dresscale", "dw_resrand1", "dcapscale"]

# --- freq-Tabelle
data = defaultdict(dict)          # inst -> {vg1: freq}
for r in csv.DictReader(open(freq_csv)):
    if r["Corner"] != "nom":
        data[int(r["mc_iteration"])][float(r["VG1"])] = float(r["freq"] or 0)
vgs = sorted({v for d in data.values() for v in d})
missing = [(i, v) for i in data for v in vgs if v not in data[i]]
print(f"Instanzen: {len(data)}, VG1-Werte: {len(vgs)} ({vgs[0]:g}–{vgs[-1]:g} V), fehlend: {len(missing)}")
nonmono = [i for i, d in data.items()
           if any(d[a] > 0 and d[b] == 0 for a in vgs for b in vgs if b > a)]
print("Nicht monoton:", nonmono or "keine")

# --- Schwelle je Instanz (Intervall letztes 0 .. erstes > 0)
th = {}
for i, d in sorted(data.items()):
    lo = max((v for v in vgs if d[v] == 0), default=None)
    hi = min((v for v in vgs if d[v] > 0), default=None)
    th[i] = (lo, hi)
never = [i for i, (lo, hi) in th.items() if hi is None]
always = [i for i, (lo, hi) in th.items() if lo is None]
ok = {i: (lo + hi) / 2 for i, (lo, hi) in th.items() if lo is not None and hi is not None}
print(f"Feuert nie (bis {vgs[-1]:g} V): {never or 'keine'} · feuert schon ab {vgs[0]:g} V: {always or 'keine'}")
m = sorted(ok.values())
print(f"\nSchwelle (n = {len(m)}): μ = {st.mean(m)*1000:.0f} mV, σ = {st.stdev(m)*1000:.0f} mV, "
      f"Median {st.median(m)*1000:.0f} mV, Spanne {m[0]*1000:.0f}–{m[-1]*1000:.0f} mV")
print("Sortiert [mV]:", " ".join(f"{x*1000:.0f}" for x in m))

# --- Anteil feuernder Chips je VG1
print("\nAnteil feuernder Chips:")
for v in vgs:
    n = sum(d[v] > 0 for d in data.values())
    if 0 < n < len(data) or v in (vgs[0], 1.0, vgs[-1]):
        print(f"  {v:.2f} V: {n:2d}/{len(data)}")

# --- Frequenzstreuung bei festen VG1
print("\nFrequenz über Instanzen (nur feuernde):")
for v in (1.0, 1.1, 1.2, 1.3, 1.5):
    f = [d[v] for d in data.values() if d[v] > 0]
    if len(f) > 1:
        print(f"  {v:.1f} V: μ = {st.mean(f)/1e3:.2f} kHz, σ/μ = {st.stdev(f)/st.mean(f)*100:.1f} %, "
              f"{min(f)/1e3:.2f}–{max(f)/1e3:.2f} kHz (n = {len(f)})")
onset = [data[i][hi] for i, (lo, hi) in th.items() if hi is not None]
print(f"f beim ersten Feuern: {min(onset)/1e3:.2f}–{max(onset)/1e3:.2f} kHz")

# --- Process-θ einlesen
names = [l.split()[-1] for l in open(params_txt) if l.strip() and not l.startswith("#")]
rows = [[float(x) for x in l.split()] for l in open(theta_txt) if l.strip()]
print(f"\nθ_process: {len(rows)} Instanzen × {len(rows[0])} Werte, {len(names)} Namen")
idx = [names.index(n) for n in RELEVANT]
theta = {i + 1: [r[k] for k in idx] for i, r in enumerate(rows)}   # Zeile i ↔ mc_iteration i+1
T = np.array([theta[i] for i in data])
print("θ-Statistik (relevante 9): μ ∈ [{:.2f}, {:.2f}], σ ∈ [{:.2f}, {:.2f}]".format(
    T.mean(0).min(), T.mean(0).max(), T.std(0, ddof=1).min(), T.std(0, ddof=1).max()))

# --- Schwelle ↔ θ: Korrelation und lineare Regression
ids = sorted(ok)
X = np.array([theta[i] for i in ids]); y = np.array([ok[i] for i in ids]) * 1000
print(f"\nKorrelation θ ↔ Schwelle (n = {len(ids)}):")
for k in sorted(range(len(RELEVANT)), key=lambda k: -abs(np.corrcoef(X[:, k], y)[0, 1])):
    print(f"  {RELEVANT[k]:12s} r = {np.corrcoef(X[:, k], y)[0, 1]:+.2f}")
A = np.c_[np.ones(len(ids)), X]
coef, *_ = np.linalg.lstsq(A, y, rcond=None)
res = y - A @ coef
print(f"Linearer Fit Schwelle = a + Σ b·θ: a = {coef[0]:.0f} mV, R² = {1 - res.var() / y.var():.3f}, "
      f"Rest-σ = {res.std(ddof=len(coef)):.1f} mV")
print("  b [mV/σ]: " + ", ".join(f"{n} {b:+.0f}" for n, b in zip(RELEVANT, coef[1:]) if abs(b) >= 5))

# --- Frequenz bei 1,5 V ↔ θ (relativ, in % je σ)
y = np.array([data[i][1.5] for i in ids]); y = (y / y.mean() - 1) * 100
coef, *_ = np.linalg.lstsq(A, y, rcond=None)
res = y - A @ coef
print(f"\nLinearer Fit f(1,5 V) [% um μ]: R² = {1 - res.var() / y.var():.3f}, Rest-σ = {res.std(ddof=len(coef)):.1f} %")
print("  b [%/σ]: " + ", ".join(f"{n} {b:+.1f}" for n, b in zip(RELEVANT, coef[1:]) if abs(b) >= 1))
