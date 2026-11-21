"""Signale für den V/T-Prüfstein (Checkliste 23).

Nutzung: python make_vt23.py <Ordner mit Testsignalen> <Zielordner>
Schreibt die Originale (für die Ecken) und je Ecke die umgerechnete Version für das nominale Neuron:
u(τ) = Vg1(τ / k) − ΔVth, τ = 0 … 5,5 ms im 1-µs-Raster (Außenmodell, Plan 3.3).
"""
import sys, shutil
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # make_stimuli liegt in scripts/
from make_stimuli import write, typ_c

# Ecke: (VDD, T, ΔVth in V, k) – ΔVth aus VT fein (Punkt 14), k = f_Ecke / f_nom bei VG1 1,1 / 1,25 V
CORNERS = {"V1.35_T10": (1.35, 10, -0.008, 0.880), "V1.35_T35": (1.35, 35, -0.026, 1.018),
           "V1.65_T10": (1.65, 10, 0.034, 0.923), "V1.65_T35": (1.65, 35, 0.018, 1.071)}
if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    orig, nom = dst / "orig", dst / "nom"
    orig.mkdir(parents=True, exist_ok=True); nom.mkdir(parents=True, exist_ok=True)
    for name in ("A_1v20", "B_steps", "C_sine", "E_noise"):
        shutil.copy(src / f"{name}.pwl", orig / f"{name}.pwl")
    write(orig / "S_sine800.pwl", *typ_c(0.98, [(0.12, 800, 0.0)]))      # reiner Sinus um die Schwelle

    tau = np.arange(0, 5.5e-3 + 0.5e-6, 1e-6)
    for f in sorted(orig.glob("*.pwl")):
        t, v = np.loadtxt(f, unpack=True)
        for c, (_, _, dv, k) in CORNERS.items():
            u = np.interp(tau / k, t, v) - dv                               # hinter 5 ms: letzter Wert
            write(nom / f"{f.stem}__{c}.pwl", tau, np.clip(u, 0, None))
    print(len(list(orig.glob("*.pwl"))), "Originale,", len(list(nom.glob("*.pwl"))), "umgerechnete Signale")
