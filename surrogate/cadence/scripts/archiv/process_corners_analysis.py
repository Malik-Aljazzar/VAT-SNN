"""Process-Ecken × VG1-Sweep auswerten (Checkliste Punkt 9).

Nutzung: python process_corners_analysis.py <csv aus ADE XL, Detail-Transpose>
Erkennt die Model-Section-Spalten automatisch (Werte typ/fas/slo/nom/min/max).
"""
import csv, sys
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

SECTIONS = {"typ", "fas", "slo", "nom", "min", "max"}
rows = [r for r in csv.DictReader(open(sys.argv[1])) if r["Corner"] != "nom"]
cols = list(rows[0].keys())
sec_cols = [c for c in cols if c not in ("Corner", "Point") and rows and
            {r[c] for r in rows} <= SECTIONS and {r[c] for r in rows}]
print("Section-Spalten:", sec_cols)

data = defaultdict(dict)                       # (sections) -> {vg1: freq}
for r in rows:
    key = tuple(r[c] for c in sec_cols) if sec_cols else (r["Corner"],)
    data[key][float(r["VG1"])] = float(r["freq"] or 0)
vgs = sorted({v for d in data.values() for v in d})

def threshold(d):
    lo = max((v for v in vgs if d.get(v, 0) == 0), default=None)
    hi = min((v for v in vgs if d.get(v, 0) > 0), default=None)
    return lo, hi

def mid(t):
    return (t[0] + t[1]) / 2 if None not in t else float("nan")

nom_key = next((k for k in data if set(k) <= {"typ", "nom"}), None)
nom = data[nom_key]
th_nom = mid(threshold(nom))
print(f"Referenz {nom_key}: Schwelle {threshold(nom)} V")

ref_v = [v for v in (1.0, 1.2, 1.5) if v in vgs]
print(f"\n{'Ecke':28s} {'Schwelle (V)':>14s} {'ΔSchw (mV)':>11s} " +
      " ".join(f"{'Δf@'+format(v,'g')+'V':>10s}" for v in ref_v))

def line(k):
    d = data[k]; t = threshold(d)
    df = [(d[v] / nom[v] - 1) * 100 if nom.get(v) else float("nan") for v in ref_v]
    ts = f"< {t[1]}" if t[0] is None else (f"> {t[0]}" if t[1] is None else f"{t[0]}–{t[1]}")
    ds = f"{(mid(t)-th_nom)*1000:+11.0f}" if None not in t else f"{'(' + ('<' if t[0] is None else '>') + ')':>11s}"
    print(f"{'/'.join(k):28s} {ts:>14s} {ds} " +
          " ".join(f"{x:+9.1f}%" for x in df))

n_nondefault = lambda k: sum(s not in ("typ", "nom") for s in k)
print("— Einzeleffekte —")
for k in sorted(data, key=lambda k: (n_nondefault(k), k)):
    if n_nondefault(k) == 1:
        line(k)
print("— Kombinationen —")
for k in sorted(data, key=lambda k: (threshold(data[k])[1] or 9)):
    if n_nondefault(k) >= 2:
        line(k)
