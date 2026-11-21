"""Plot one example per signal type from an assembled dataset (check after gen_dataset.py assemble).

Usage: python plots/plot_dataset_samples.py <Name> <chip> <output.png>
"""
# sys: command-line arguments; csv: CSV files
import sys, csv
# Path: convenient handling of file and folder paths
from pathlib import Path
# numpy: arrays and maths
import numpy as np
# matplotlib: plots
import matplotlib
# backend "Agg": draw into files only, never open a window
matplotlib.use("Agg")
# plotting interface of matplotlib
import matplotlib.pyplot as plt

# dataset name, chip number and output file from the arguments
name, chip, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
# dataset folder 03_Cadence/datasets/<Name> (two levels above this script)
D = Path(__file__).resolve().parents[2] / "datasets" / name
# load the raw data
d = np.load(D / f"{name}_raw.npz")
# index rows (one per simulation)
idx = list(csv.DictReader(open(D / "index.csv")))
# colours: input (blue), output (orange), grey for axis labels
C_IN, C_OUT, MUTED = "#2a78d6", "#eb6834", "#52514e"
# the chosen simulations (one per type)
picks = []
# For every signal type
for typ in "ABCD":
    # the first simulation of this type with this chip (None if there is none)
    r = next((r for r in idx if r["typ"] == typ and int(r["chip"]) == chip), None)
    # if one was found:
    if r:
        # take it
        picks.append(r)
# one plot per chosen simulation, stacked vertically, with a shared time axis
fig, axes = plt.subplots(len(picks), 1, figsize=(10, 1.9 * len(picks)), sharex=True)
# For every plot and its simulation (atleast_1d: works also when there is only one plot)
for ax, r in zip(np.atleast_1d(axes), picks):
    # row of the simulation in the npz file; time in ms
    n = int(r["n"]); t = d["t"] * 1e3
    # output vout (orange, thin line)
    ax.plot(t, d["vout"][n], color=C_OUT, lw=0.8, label="vout")
    # input vg1 (blue, thicker line)
    ax.plot(t, d["vg1"][n], color=C_IN, lw=1.5, label="vg1")
    # title: type, signal file, chip, VDD and T
    ax.set_title(f"Typ {r['typ']} · {r['signal']} · Chip {chip} · VDD {float(r['vdd']):.3f} V, T {float(r['temp']):.1f} °C",
                 loc="left", fontsize=9)
    # voltage axis from −0.05 to 1.7 V; small grey axis numbers
    ax.set_ylim(-0.05, 1.7); ax.tick_params(labelsize=8, colors=MUTED)
    # the upper and the right frame line …
    for s in ("top", "right"):
        # … are hidden
        ax.spines[s].set_visible(False)
# legend in the top plot
np.atleast_1d(axes)[0].legend(loc="upper right", frameon=False, fontsize=8, ncol=2)
# label of the time axis in the bottom plot
np.atleast_1d(axes)[-1].set_xlabel("t (ms)", color=MUTED)
# arrange the plots, save the figure and print the file name
fig.tight_layout(); fig.savefig(out, dpi=100); print(out)
