"""Lauf „All“ (Process + Mismatch) gegen Process-Lauf vergleichen (Checkliste Punkt 11).

Nutzung: python all_vs_process.py <n_all> <n_process>
Liest aus 03_Cadence/exports: MC<n>_freq.csv, MC<n>_theta_process(.._params).txt, MC<n_all>_theta.txt
"""
import csv, sys, statistics as st
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

EXP = Path(__file__).resolve().parents[2] / "exports"
RELEVANT = ["norm_vfbo", "norm_vfbl", "norm_uo", "norm_xcoro", "norm_xcorl", "norm_lovo",
            "dresscale", "dw_resrand1", "dcapscale"]
n_all, n_proc = sys.argv[1:3]

def thresholds(n):
    data = defaultdict(dict)
    for r in csv.DictReader(open(EXP / f"MC{n}_freq.csv")):
        if r["Corner"] != "nom":
            data[int(r["mc_iteration"])][float(r["VG1"])] = float(r["freq"] or 0)
    vgs = sorted({v for d in data.values() for v in d})
    th = {}
    for i, d in data.items():
        lo = max((v for v in vgs if d[v] == 0), default=None)
        hi = min((v for v in vgs if d[v] > 0), default=None)
        th[i] = (lo + hi) / 2 * 1000 if None not in (lo, hi) else float("nan")
    nonmono = [i for i, d in data.items() if any(d[a] > 0 and d[b] == 0 for a in vgs for b in vgs if b > a)]
    return th, data, nonmono

def theta_process(n):
    names = [l.split()[-1] for l in open(EXP / f"MC{n}_theta_process_params.txt") if l.strip() and not l.startswith("#")]
    rows = [[float(x) for x in l.split()] for l in open(EXP / f"MC{n}_theta_process.txt") if l.strip()]
    idx = [names.index(p) for p in RELEVANT]
    return {i + 1: np.array([r[k] for k in idx]) for i, r in enumerate(rows)}

th_a, data_a, nm_a = thresholds(n_all)
th_p, _, _ = thresholds(n_proc)
tp_a, tp_p = theta_process(n_all), theta_process(n_proc)
print(f"MC{n_all}: {len(th_a)} Chips, {sum(len(d) for d in data_a.values())} Sims, nicht monoton: {nm_a or 'keine'}")
print(f"Mismatch-θ vorhanden: {(EXP / f'MC{n_all}_theta.txt').exists()}")

same = all(np.allclose(tp_a[i], tp_p[i]) for i in tp_a if i in tp_p)
print(f"Process-θ MC{n_all} = MC{n_proc} (gleicher Seed): {'ja' if same else 'nein'}")

v = [x for x in th_a.values() if x == x]
print(f"\nSchwelle MC{n_all}: μ = {st.mean(v):.0f} mV, σ = {st.stdev(v):.0f} mV (n = {len(v)}), erwartet σ ≈ 59 mV")

# Process-Anteil per linearem Fit aus MC<n_proc> vorhersagen, Rest = Mismatch (+ Fit-/Rasterfehler)
ids = sorted(i for i in th_p if th_p[i] == th_p[i])
A = np.c_[np.ones(len(ids)), [tp_p[i] for i in ids]]
coef, *_ = np.linalg.lstsq(A, np.array([th_p[i] for i in ids]), rcond=None)
print(f"\n{'Chip':>4s} {'MC' + n_all:>7s} {'Fit':>7s} {'Δ':>6s}" + (f" {'MC' + n_proc:>7s} {'Δ':>6s}" if same else ""))
d_fit, d_same = [], []
for i in sorted(th_a):
    pred = coef[0] + coef[1:] @ tp_a[i]
    d_fit.append(th_a[i] - pred)
    line = f"{i:4d} {th_a[i]:7.0f} {pred:7.0f} {d_fit[-1]:+6.0f}"
    if same:
        d_same.append(th_a[i] - th_p[i]); line += f" {th_p[i]:7.0f} {d_same[-1]:+6.0f}"
    print(line)
print(f"σ(Δ zum Fit) = {np.std(d_fit, ddof=1):.1f} mV (erwartet ≈ √(10² + 10²) ≈ 14 mV: Mismatch + Fit-Rest)")
if same:
    print(f"σ(Δ zu MC{n_proc}) = {np.std(d_same, ddof=1):.1f} mV (erwartet ≈ 10 mV: nur Mismatch, Raster 10 mV)")
