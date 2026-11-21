"""Testsignale A/B/C/E: Eingang vg1 und Ausgang vout des nominalen Neurons (Checkliste 19).

Nutzung: python plot_pwl_test.py <Ordner mit *.csv aus pwl_check.sh> <Ausgabe.png>
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder, out = Path(sys.argv[1]), sys.argv[2]
C_IN, C_OUT, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"   # Kategorie 1/2, Text
files = sorted(folder.glob("*.csv"))
fig, axes = plt.subplots(len(files), 1, figsize=(10, 2.3 * len(files)), sharex=True)
for ax, f in zip(np.atleast_1d(axes), files):
    d = np.genfromtxt(f, delimiter=",", names=True)
    t = d["t"] * 1e3
    ax.plot(t, d["vout"], color=C_OUT, lw=1, label="vout")
    ax.plot(t, d["vg1"], color=C_IN, lw=2, label="vg1 (Eingang)")
    ax.axhline(0.75, color=MUTED, lw=0.8, ls=":")
    ax.set_title(f.stem, loc="left", fontsize=10, color=INK)
    ax.set_ylabel("V", color=MUTED); ax.set_ylim(-0.05, 1.7)
    ax.grid(axis="y", color="#e5e4e0", lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED)
axes[0].legend(loc="upper right", frameon=False, ncol=2, fontsize=9)
axes[-1].set_xlabel("t (ms)", color=MUTED)
fig.text(0.99, 0.005, "gepunktet: VDD/2 = 0,75 V (Spike-Kriterium)", ha="right", fontsize=8, color=MUTED)
fig.tight_layout()
fig.savefig(out, dpi=110)
print(out)
