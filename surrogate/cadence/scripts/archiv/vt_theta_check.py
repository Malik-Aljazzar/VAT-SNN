"""Gilt dasselbe ΔVth(ω) und k(ω) für jeden Chip? (Checkliste Punkt 15)

Nutzung: python vt_theta_check.py <n_vt> <n_ref>
  n_vt:  MC-Lauf an den V/T-Ecken (z. B. 19), n_ref: derselbe Seed bei 1,5 V / 27 °C (z. B. 18)
Liest aus 03_Cadence/exports: MC<n>_freq.csv und (falls vorhanden) MC<n>_theta*.txt
"""
import csv, sys, re
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

EXP = Path(__file__).resolve().parents[2] / "exports"
n_vt, n_ref = sys.argv[1:3]
K_VG1 = (1.15, 1.2, 1.25)             # k nur deutlich über der Schwelle und ≤ 1,25 V (bei VDD 1,35 V sonst VG1 > VDD)

def load(n):
    """-> {corner: {chip: {vg1: freq}}}, {corner: Beschreibung}"""
    data = defaultdict(lambda: defaultdict(dict)); desc = {}
    for r in csv.DictReader(open(EXP / f"MC{n}_freq.csv")):
        if r["Corner"] == "nom":
            continue
        c = re.sub(r"_\d+$", "", r["Corner"])
        data[c][int(r["mc_iteration"])][float(r["VG1"])] = float(r["freq"] or 0)
        extra = {k: v for k, v in r.items() if k.lower() in ("vdd", "temperature", "temp")}
        desc[c] = " ".join(f"{k}={v}" for k, v in extra.items()) or c
    return data, desc

def threshold(d):
    v = sorted(d)
    lo = max((a for a in v if d[a] == 0), default=None)
    hi = min((a for a in v if d[a] > 0), default=None)
    return (lo + hi) / 2 * 1000 if None not in (lo, hi) else float("nan")

def theta(n):
    p = EXP / f"MC{n}_theta_process.txt"; m = EXP / f"MC{n}_theta.txt"
    tp = [l.split() for l in open(p) if l.strip()] if p.exists() else None
    tm = [l.split() for l in open(m) if l.strip() and not l.startswith("#")] if m.exists() else None
    return tp, tm

# Chip-Identität prüfen
tp_v, tm_v = theta(n_vt); tp_r, tm_r = theta(n_ref)
if tp_v and tp_r:
    k = min(len(tp_v), len(tp_r))
    print(f"Process-θ MC{n_vt} = MC{n_ref}: {'ja' if tp_v[:k] == tp_r[:k] else 'NEIN'}")
if tm_v and tm_r:
    k = min(len(tm_v), len(tm_r))
    print(f"Mismatch-θ MC{n_vt} = MC{n_ref}: {'ja' if tm_v[:k] == tm_r[:k] else 'NEIN'}")

ref_all, _ = load(n_ref)
ref = next(iter(ref_all.values()))                 # Referenzlauf hat eine Corner-Gruppe
vt, desc = load(n_vt)
for c, chips in vt.items():
    print(f"\n##### {c} ({desc[c]})")
    print(f"{'Chip':>4s} {'th_ref':>7s} {'th':>6s} {'ΔVth':>6s} " + " ".join(f"{'k@' + format(v, 'g'):>7s}" for v in K_VG1))
    rows = []
    for i in sorted(chips):
        if i not in ref:
            continue
        tr, tv = threshold(ref[i]), threshold(chips[i])
        ks = [chips[i][v] / ref[i][v] if ref[i].get(v) and chips[i].get(v) else float("nan") for v in K_VG1]
        rows.append((tr, tv - tr, *ks))
        print(f"{i:4d} {tr:7.0f} {tv:6.0f} {tv - tr:+6.0f} " + " ".join(f"{x:7.3f}" for x in ks))
    a = np.array(rows)
    dv, kk = a[:, 1], np.nanmean(a[:, 2:], axis=1)
    print(f"ΔVth: μ = {np.nanmean(dv):+.1f} mV, σ = {np.nanstd(dv, ddof=1):.1f} mV "
          f"(Raster 10 mV → σ ≈ 4 mV allein durch Rasterung), Korrelation mit th_ref r = {np.corrcoef(a[:, 0], dv)[0, 1]:+.2f}")
    print(f"k (Mittel über {K_VG1}): μ = {np.nanmean(kk):.3f}, σ = {np.nanstd(kk, ddof=1):.3f} "
          f"({np.nanstd(kk, ddof=1) / np.nanmean(kk) * 100:.1f} %), Korrelation mit th_ref r = {np.corrcoef(a[:, 0], kk)[0, 1]:+.2f}")
    drift = np.nanmax(a[:, 2:], axis=1) / np.nanmin(a[:, 2:], axis=1) - 1
    print(f"k-Drift über VG1 je Chip: max {np.nanmax(drift) * 100:.1f} %")
