"""Mini-Pilot einlesen, θ-Konsistenz prüfen, plotten (Checkliste Punkte 21/22).

Nutzung: python pilot_check.py <Ordner aus direct_mc_pwl.sh> <Ausgabe.png> [<Referenz-MC-Nr. für θ, z. B. 18>]
Prüft: alle Signale haben dieselben θ je Chip (Process + Mismatch); optional gleich wie ADE-Lauf MC<n>.
Plot: Zeilen = Signale, Spalten = Chips; vg1 und vout.
"""
import sys, re
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.stdout.reconfigure(encoding="utf-8")

folder, out = Path(sys.argv[1]), sys.argv[2]
ref = sys.argv[3] if len(sys.argv) > 3 else None
EXP = Path(__file__).resolve().parents[2] / "exports"

def read_process(p):
    return [l.split() for l in open(p) if l.strip()]

def read_mismatch(p):
    rows, cur = {}, None
    for l in open(p):
        t = l.strip()
        if t.startswith("#"):
            cur = int(t[1:])
        elif t:
            rows[cur] = t.split()
    return [rows[k] for k in sorted(rows)]

# --- θ-Konsistenz über Signale
th = folder / "theta"
stims = sorted({re.sub(r"_(processData|processParam|mismatchData|mismatchParam)$", "", p.name) for p in th.iterdir()})
P = {s: read_process(th / f"{s}_processData") for s in stims}
M = {s: read_mismatch(th / f"{s}_mismatchData") for s in stims}
same_p = all(P[s] == P[stims[0]] for s in stims); same_m = all(M[s] == M[stims[0]] for s in stims)
print(f"Signale: {stims}")
print(f"Process-θ über alle Signale gleich: {same_p} · Mismatch-θ gleich: {same_m} · Chips: {len(P[stims[0]])}")
if ref:
    rp = read_process(EXP / f"MC{ref}_theta_process.txt"); rm = read_mismatch(EXP / f"MC{ref}_theta.txt")
    n = len(P[stims[0]])
    print(f"Gleich wie ADE MC{ref} (erste {n} Chips): Process {P[stims[0]] == rp[:n]}, Mismatch {M[stims[0]] == rm[:n]}")

# --- Verläufe
files = sorted(folder.glob("*_i*.csv"))
chips = sorted({int(re.search(r"_i(\d+)\.csv$", f.name).group(1)) for f in files})
C_IN, C_OUT, INK, MUTED = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e"
fig, axes = plt.subplots(len(stims), len(chips), figsize=(3.0 * len(chips), 2.0 * len(stims)), sharex=True, sharey=True)
axes = np.atleast_2d(axes)
for r, s in enumerate(stims):
    for c, i in enumerate(chips):
        ax = axes[r, c]
        d = np.genfromtxt(folder / f"{s}_i{i:03d}.csv", delimiter=",", names=True)
        t = d["t"] * 1e3
        ax.plot(t, d["vout"], color=C_OUT, lw=0.8, label="vout")
        ax.plot(t, d["vg1"], color=C_IN, lw=1.6, label="vg1")
        ax.axhline(0.75, color=MUTED, lw=0.6, ls=":")
        n_sp = np.sum((d["vout"][:-1] < 0.75) & (d["vout"][1:] >= 0.75))
        ax.text(0.98, 0.04, f"{n_sp} Spikes", transform=ax.transAxes, ha="right", fontsize=7, color=MUTED)
        if r == 0:
            ax.set_title(f"Chip {i}", fontsize=9, color=INK)
        if c == 0:
            ax.set_ylabel(s, fontsize=8, color=INK)
        ax.set_ylim(-0.05, 1.7); ax.tick_params(labelsize=7, colors=MUTED)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
axes[0, -1].legend(loc="upper right", frameon=False, fontsize=7)
for ax in axes[-1]:
    ax.set_xlabel("t (ms)", fontsize=8, color=MUTED)
fig.tight_layout()
fig.savefig(out, dpi=100)
print(out)
