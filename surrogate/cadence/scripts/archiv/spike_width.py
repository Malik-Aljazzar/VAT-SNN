"""Spikeform von vout messen → Trainings-Δt (Checkliste Punkt 16).

Nutzung: python spike_width.py <Ordner mit vg<VG1>_i<iter>.txt aus remote_waves.sh> [VDD]
Misst im Fenster 1–5 ms je Spike: Breite über VDD/2, Basisbreite über 10 % der Amplitude,
Anstiegs- und Abfallzeit (10–90 %), Periode; und wie viele Abtastpunkte bei Δt = 1/5/10/20 µs
im Spike (über VDD/2) liegen.
"""
import sys, re
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

folder = Path(sys.argv[1]); vdd = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5

def load(f):
    rows = [l.split() for l in open(f) if re.match(r"\s*[0-9.]+e[+-]\d+", l)]
    a = np.array(rows, dtype=float)
    return a[:, 0], a[:, 2]                      # t, vout

def crossings(t, y, level):
    s = y > level
    up = np.where(~s[:-1] & s[1:])[0]; dn = np.where(s[:-1] & ~s[1:])[0]
    lin = lambda i: t[i] + (level - y[i]) * (t[i + 1] - t[i]) / (y[i + 1] - y[i])
    return np.array([lin(i) for i in up]), np.array([lin(i) for i in dn])

res = {}
for f in sorted(folder.glob("vg*_i*.txt")):
    vg = f.name.split("_")[0][2:]
    t, v = load(f)
    m = (t >= 1e-3) & (t <= 5e-3); t, v = t[m], v[m]
    lo, hi = np.percentile(v, 1), v.max()
    amp = hi - lo
    w50 = []; w10 = []; tr = []; tf = []
    up50, dn50 = crossings(t, v, vdd / 2)
    if len(up50) < 2:                            # Chip feuert bei diesem VG1 nicht
        continue
    up10, dn10 = crossings(t, v, lo + 0.1 * amp)
    up90, dn90 = crossings(t, v, lo + 0.9 * amp)
    for u in up50:
        d = dn50[dn50 > u]
        if len(d): w50.append(d[0] - u)
    for u in up10:
        d = dn10[dn10 > u]
        if len(d): w10.append(d[0] - u)
        a = up90[up90 > u]
        if len(a): tr.append(a[0] - u)
    for d in dn90:
        e = dn10[dn10 > d]
        if len(e): tf.append(e[0] - d)
    per = np.diff(up50)
    # Abtastpunkte über VDD/2 bei gröberem Raster (alle Phasenlagen gemittelt)
    pts = {dt: np.mean([len(np.arange(np.ceil((u - ph) / dt) * dt + ph, d, dt))
                        for u, d in zip(up50, dn50[dn50 > up50[0]]) for ph in np.linspace(0, dt, 5, endpoint=False)])
           for dt in (1e-6, 5e-6, 10e-6, 20e-6)}
    res.setdefault(vg, []).append((np.median(w50), np.median(w10), np.median(tr), np.median(tf), np.median(per), amp,
                                   pts[1e-6], pts[5e-6], pts[10e-6], pts[20e-6]))

for vg, r in res.items():
    a = np.array(r)
    print(f"VG1 = {vg} V ({len(r)} Chips):")
    names = ["Breite über VDD/2", "Basisbreite (10 %)", "Anstieg 10–90 %", "Abfall 90–10 %", "Periode"]
    for k, n in enumerate(names):
        print(f"  {n:20s} {np.mean(a[:, k]) * 1e6:7.1f} µs  ({np.min(a[:, k]) * 1e6:.1f}–{np.max(a[:, k]) * 1e6:.1f})")
    print(f"  {'Amplitude':20s} {np.mean(a[:, 5]):7.3f} V")
    print("  Punkte über VDD/2 je Spike bei Δt = 1 / 5 / 10 / 20 µs: " +
          " / ".join(f"{np.mean(a[:, k]):.1f}" for k in (6, 7, 8, 9)))
