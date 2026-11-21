"""V/T-Prüfstein auswerten (Checkliste 23): Ecke vs. nominales Neuron mit umgerechnetem Eingang.

Nutzung: python vt23_compare.py <exports-Ordner> <Ausgabe.png>
Erwartet exports/vt23_<Ecke>/<Signal>.csv, vt23_nom/<Signal>__<Ecke>.csv, vt23_nom_orig/<Signal>.csv.
Modell (Plan 3.3): vout_Ecke(t) ≈ VDD/1,5 · vout_nom(k·t) bei Eingang Vg1(τ/k) − ΔVth.
Vergleich: steigende Durchgänge durch VDD/2 (Spikebeginn), Breite über VDD/2, RMS-Fehler.
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from make_vt23 import CORNERS

ex, out = Path(sys.argv[1]), sys.argv[2]
SIGS = ["A_1v20", "B_steps", "C_sine", "E_noise", "S_sine800"]
TOL = 40e-6                                    # Spikes gelten als gleich, wenn |Δt| < 40 µs

def load(p):
    d = np.genfromtxt(p, delimiter=",", names=True)
    return d["t"], d["vout"]

def spikes(t, v, lvl):
    s = v >= lvl
    up = np.where(~s[:-1] & s[1:])[0]; dn = np.where(s[:-1] & ~s[1:])[0]
    lin = lambda i: t[i] + (lvl - v[i]) * (t[i + 1] - t[i]) / (v[i + 1] - v[i])
    ups = np.array([lin(i) for i in up]); dns = np.array([lin(i) for i in dn])
    w = np.array([dns[dns > u][0] - u for u in ups if np.any(dns > u)])
    return ups, w

def match(a, b):
    """Spikes a (Ecke) und b (Modell) paaren → Δt der Paare, Anzahl fehlend/zusätzlich."""
    used, dts = set(), []
    for x in a:
        j = np.argmin(np.abs(b - x)) if len(b) else None
        if j is not None and abs(b[j] - x) < TOL and j not in used:
            used.add(j); dts.append(b[j] - x)
    return np.array(dts), len(a) - len(dts), len(b) - len(used)

print(f"{'Ecke':10s} {'Signal':10s} {'Spikes E/M/nom':>14s} {'fehlt/extra':>11s} {'|Δt| Ø/max (µs)':>16s} "
      f"{'Breite E/M (µs)':>16s} {'RMS M / nom':>12s}")
summary = []
for c, (vdd, temp, dv, k) in CORNERS.items():
    for s in SIGS:
        tc, vc = load(ex / f"vt23_{c}" / f"{s}.csv")
        tn, vn = load(ex / "vt23_nom" / f"{s}__{c}.csv")
        to, vo = load(ex / "vt23_nom_orig" / f"{s}.csv")
        tm, vm = tn / k, vn * vdd / 1.5                      # Modell auf Zeitachse der Ecke
        m = tm <= 5e-3
        uc, wc = spikes(tc, vc, vdd / 2); um, wm = spikes(tm[m], vm[m], vdd / 2); uo, _ = spikes(to, vo * vdd / 1.5, vdd / 2)
        dts, miss, extra = match(uc, um)
        grid = np.arange(0.2e-3, 5e-3, 1e-6)
        rms_m = np.sqrt(np.mean((np.interp(grid, tc, vc) - np.interp(grid, tm, vm)) ** 2))
        rms_o = np.sqrt(np.mean((np.interp(grid, tc, vc) - np.interp(grid, to, vo * vdd / 1.5)) ** 2))
        dt_s = f"{np.mean(np.abs(dts)) * 1e6:5.1f} / {np.max(np.abs(dts)) * 1e6:5.1f}" if len(dts) else "–"
        w_s = f"{np.mean(wc) * 1e6:5.1f} / {np.mean(wm) * 1e6:5.1f}" if len(wc) and len(wm) else "–"
        print(f"{c:10s} {s:10s} {len(uc):4d}/{len(um):3d}/{len(uo):3d}   {miss:4d}/{extra:<4d}  {dt_s:>16s} {w_s:>16s} "
              f"{rms_m:5.3f} / {rms_o:5.3f}")
        summary.append((c, s, len(uc), miss, extra, np.mean(np.abs(dts)) if len(dts) else np.nan, rms_m, rms_o))

a = np.array([(x[2], x[3], x[4], x[5], x[6], x[7]) for x in summary], dtype=float)
print(f"\nGesamt: {int(a[:, 0].sum())} Spikes an den Ecken, fehlend {int(a[:, 1].sum())}, zusätzlich {int(a[:, 2].sum())}; "
      f"Ø |Δt| = {np.nanmean(a[:, 3]) * 1e6:.1f} µs; RMS Modell {a[:, 4].mean():.3f} V vs. ohne Außenmodell {a[:, 5].mean():.3f} V")

# Plot: Sinus-Signal an allen 4 Ecken, Ecke vs. Modell vs. ohne Außenmodell
C_E, C_M, C_O, MUTED = "#eb6834", "#2a78d6", "#8f8d87", "#52514e"
fig, axes = plt.subplots(len(CORNERS), 1, figsize=(10, 2.2 * len(CORNERS)), sharex=True)
for ax, (c, (vdd, temp, dv, k)) in zip(axes, CORNERS.items()):
    s = "C_sine"
    tc, vc = load(ex / f"vt23_{c}" / f"{s}.csv"); tn, vn = load(ex / "vt23_nom" / f"{s}__{c}.csv")
    to, vo = load(ex / "vt23_nom_orig" / f"{s}.csv")
    ax.plot(to * 1e3, vo * vdd / 1.5, color=C_O, lw=0.8, label="nominal, ohne Außenmodell")
    ax.plot(tc * 1e3, vc, color=C_E, lw=1.6, label="Ecke (SPICE)")
    ax.plot(tn / k * 1e3, vn * vdd / 1.5, color=C_M, lw=1.0, ls="--", label="nominal + Außenmodell")
    ax.set_title(f"{c.replace('_', ' / ').replace('V', '').replace('T', '')}  (ΔVth {dv * 1e3:+.0f} mV, k = {k})",
                 loc="left", fontsize=9)
    ax.set_xlim(0, 5); ax.set_ylabel("vout (V)", color=MUTED, fontsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(labelsize=8, colors=MUTED)
axes[0].legend(loc="upper right", frameon=False, fontsize=8, ncol=3)
axes[-1].set_xlabel("t (ms)", color=MUTED)
fig.tight_layout(); fig.savefig(out, dpi=100)
print(out)
