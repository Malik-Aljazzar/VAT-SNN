"""Plots für die V/T-Corner-Auswertung (Kennlinie + Schwellen-Zoom als Achsen-Schnitte, dazu alle 9 Ecken).

Nutzung: python plot_vt_corners.py <vt_corners_vg1_sweep.csv> <ausgabeordner>
"""
import csv, sys, os
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src, out = sys.argv[1], sys.argv[2]
data = defaultdict(list)                          # (VDD, T) -> [(VG1, f_kHz)]
for r in csv.DictReader(open(src)):
    data[(float(r["VDD"]), float(r["temperature"]))].append((float(r["VG1"]), float(r["freq"] or 0) / 1e3))
for k in data:
    data[k].sort()

colors = {0: "tab:blue", 1: "black", 2: "tab:red"}
groups = [
    ("Spannung (T = 27 °C, typ)", [((v, 27.0), f"VDD = {v:g} V") for v in (1.35, 1.5, 1.65)]),
    ("Temperatur (VDD = 1,5 V, typ)", [((1.5, t), f"T = {t:g} °C") for t in (10.0, 27.0, 35.0)]),
]

def draw(fname, xlim, title_prefix):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, (title, curves) in zip(axes, groups):
        for i, (key, label) in enumerate(curves):
            x, y = zip(*data[key])
            ax.plot(x, y, "o-", color=colors[i], label=label, ms=4)
        ax.set_title(title_prefix + title)
        ax.set_xlabel("VG1 (V)")
        ax.set_xlim(*xlim)
        ax.grid(alpha=0.3)
        ax.legend()
    axes[0].set_ylabel("Spike-Frequenz (kHz)")
    fig.tight_layout()
    fig.savefig(os.path.join(out, fname), dpi=130)
    plt.close(fig)

draw("vt_corners_freq_vs_vg1.png", (0.82, 1.52), "")
draw("vt_corners_schwelle_zoom.png", (0.88, 1.01), "Schwelle – ")

# Alle 9 Ecken: eine Spalte pro VDD mit den drei Temperaturen; oben ganzer Bereich, unten Schwelle
fig, axes = plt.subplots(2, 3, figsize=(14, 7), sharey=True)
for j, v in enumerate((1.35, 1.5, 1.65)):
    for row, xlim in enumerate([(0.82, 1.52), (0.88, 1.01)]):
        ax = axes[row, j]
        for i, t in enumerate((10.0, 27.0, 35.0)):
            x, y = zip(*data[(v, t)])
            ax.plot(x, y, "o-", color=colors[i], label=f"T = {t:g} °C", ms=4)
        ax.set_title(f"VDD = {v:g} V" + (" – Schwelle" if row else ""))
        ax.set_xlabel("VG1 (V)")
        ax.set_xlim(*xlim)
        ax.grid(alpha=0.3)
        ax.legend(loc="lower right" if row == 0 else "upper left")
for ax in axes[:, 0]:
    ax.set_ylabel("Spike-Frequenz (kHz)")
fig.tight_layout()
fig.savefig(os.path.join(out, "vt_corners_alle9.png"), dpi=130)
plt.close(fig)
print("ok")
