"""Kaskadentest: Verläufe aller Fälle untereinander (Daten von kaskade_waves.sh / kaskade_waves_Aaus.sh).

Nutzung: python plot_kaskade.py <Datenordner> <Ausgabe.png>
"""
import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
d, png = Path(sys.argv[1]), Path(sys.argv[2])
cases = [
    ("gnd_2M5",      "Lauf 1: Rb → GND, Rin = 2,5 MΩ (w = 0,8)"),
    ("gnd_10M",      "Lauf 1: Rb → GND, Rin = 10 MΩ (w = 0,5)"),
    ("vdd_2M5",      "Lauf 2: Rb → VDD, Rin = 2,5 MΩ (w = 0,8)"),
    ("vdd_10M",      "Lauf 2: Rb → VDD, Rin = 10 MΩ (w = 0,5)"),
    ("vdd_40M",      "Lauf 2: Rb → VDD, Rin = 40 MΩ (w = 0,2)"),
    ("vdd_10M_Aaus", "Lauf 2 mit A aus: Rin = 10 MΩ"),
    ("vdd_40M_Aaus", "Lauf 2 mit A aus: Rin = 40 MΩ"),
]
sp = lambda v: int(np.sum((v[:-1] < 0.75) & (v[1:] >= 0.75)))
fig, axs = plt.subplots(len(cases), 1, figsize=(11, 2.1 * len(cases)), sharex=True)
for ax, (n, title) in zip(axs, cases):
    a = np.genfromtxt(d / f"{n}.csv", delimiter=",", names=True)
    t = a["t"] * 1e3
    ax.plot(t, a["voutA"], color="0.6", lw=1, label="voutA (Ausgang A)")
    ax.plot(t, a["x"], color="tab:blue", lw=2, label="x = Eingang von B")
    ax.plot(t, a["voutB"], color="tab:green", lw=1.2, label="voutB (Ausgang B)")
    ax.plot(t, a["neuron1vcin"], color="tab:purple", lw=1, ls=":", label="vcin von B (Ladung)")
    ax.axhline(0.94, color="tab:red", ls="--", lw=1, label="Schwelle ≈ 0,94 V")
    ax.set_title(f"{title}   –   Spikes in 2 ms: A {sp(a['voutA'])}, B {sp(a['voutB'])}", fontsize=10, loc="left")
    ax.set_ylim(-0.05, 1.6); ax.set_ylabel("V"); ax.grid(alpha=0.3)
axs[0].legend(loc="upper right", fontsize=8, ncol=5)
axs[-1].set_xlabel("Zeit (ms)")
axs[-1].set_xlim(0, 1.2)
fig.tight_layout()
fig.savefig(png, dpi=110)
print(png)
