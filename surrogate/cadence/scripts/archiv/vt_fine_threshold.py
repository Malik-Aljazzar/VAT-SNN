"""Schwelle und Spike-Amplitude an allen V/T-Ecken, feines Raster (Checkliste Punkt 14).

Nutzung: python vt_fine_threshold.py <csv aus ADE XL, Detail-Transpose>
Erwartet Spalten für VDD und Temperatur (Name enthält „VDD“ bzw. „temp“), VG1, freq und
optional eine Amplituden-Spalte („amp“ oder Name mit „ymax“).
"""
import csv, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["Corner"] != "nom"]
cols = list(rows[0])
c_vdd = next(c for c in cols if "vdd" in c.lower())
c_t = next(c for c in cols if "temp" in c.lower())
c_amp = next((c for c in cols if "ymax" in c.lower() or c.lower() == "amp"), None)
print(f"Spalten: VDD = {c_vdd}, T = {c_t}, Amplitude = {c_amp}")

data = defaultdict(dict)                   # (VDD, T) -> {vg1: (freq, amp)}
for r in rows:
    amp = float(r[c_amp]) if c_amp and r[c_amp] not in ("", None) else float("nan")
    data[(float(r[c_vdd]), float(r[c_t]))][float(r["VG1"])] = (float(r["freq"] or 0), amp)

def threshold(d):
    v = sorted(d)
    lo = max((a for a in v if d[a][0] == 0), default=None)
    hi = min((a for a in v if d[a][0] > 0), default=None)
    return lo, hi

nom = data[(1.5, 27.0)]; lo, hi = threshold(nom); th_nom = (lo + hi) / 2
print(f"Referenz 1,5 V / 27 °C: Schwelle {lo:.3f}–{hi:.3f} V\n")
print(f"{'VDD':>5s} {'T':>4s} {'Schwelle (V)':>14s} {'ΔVth (mV)':>10s} {'Amplitude (V)':>14s} {'Amp/VDD':>8s}")
for (vdd, t) in sorted(data):
    d = data[(vdd, t)]; lo, hi = threshold(d)
    amps = [a for f, a in d.values() if f > 0 and a == a]
    amp = sum(amps) / len(amps) if amps else float("nan")
    ts = f"{lo:.3f}–{hi:.3f}" if None not in (lo, hi) else f"{lo}–{hi}"
    dv = ((lo + hi) / 2 - th_nom) * 1000 if None not in (lo, hi) else float("nan")
    print(f"{vdd:5.2f} {t:4.0f} {ts:>14s} {dv:+10.0f} {amp:14.3f} {amp / vdd:8.3f}")
