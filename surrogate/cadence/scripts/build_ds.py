"""Build the training dataset for the surrogate: split by chip + target format (checklist 30, Plan 5.4).

Usage: python build_ds.py <output name> <Name> [<Name> ...]
- Δt 10 µs: every 10th point of the 1 µs grid, 500 steps (0 … 4.99 ms)
- conditioning = θ (30, unchanged, N(0,1)) + normalised ω: (VDD − 1.5)/0.15, (T − 22.5)/12.5  → 32 values
- X = (N, 32 + 500, 1): conditioning as prefix, then vg1 · Y = (N, 500): vout
- split by chip (dataset + chip no.) 70 / 20 / 10 per dataset, seed 0
Output: datasets/<output name>/<output name>.ds (torch dict as in FlexSpike) + split.csv
"""
# sys: command-line arguments and output; csv: CSV files
import sys, csv
# Path: convenient handling of file and folder paths
from pathlib import Path
# numpy: arrays and maths
import numpy as np
# torch: tensors and saving in the format that FlexSpike reads
import torch
# print as UTF-8 (also in the Windows console)
sys.stdout.reconfigure(encoding="utf-8")

# ROOT = folder 03_Cadence (one level above the scripts folder)
ROOT = Path(__file__).resolve().parents[1]
# name of the output and the datasets to combine (from the arguments)
out_name, names = sys.argv[1], sys.argv[2:]
# STEP = take every 10th point (1 µs → 10 µs), N_T = 500 time steps, FRAC = shares train/valid/test, SEED of the split
STEP, N_T, FRAC, SEED = 10, 500, (0.7, 0.2, 0.1), 0
# X = inputs and Y = outputs, one list per part; rows = one row per simulation for split.csv
X, Y, rows = {k: [] for k in ("train", "valid", "test")}, {k: [] for k in ("train", "valid", "test")}, []
# Random number generator for the split
rng = np.random.default_rng(SEED)
# For every dataset
for name in names:
    # dataset folder 03_Cadence/datasets/<Name>
    D = ROOT / "datasets" / name
    # load the raw data
    d = np.load(D / f"{name}_raw.npz")
    # index rows (one per simulation)
    idx = list(csv.DictReader(open(D / "index.csv")))
    # key of the chip of every simulation, e.g. "ds_all:17"
    keys = [f"{name}:{r['chip']}" for r in idx]
    # all different chips (sorted) and a random order of them
    uniq = sorted(set(keys)); perm = rng.permutation(len(uniq))
    # number of chips for train (70 %) and valid (20 %); the rest goes to test
    n_tr, n_va = round(FRAC[0] * len(uniq)), round(FRAC[1] * len(uniq))
    # part of every chip: the first n_tr in the random order → train, the next n_va → valid, the rest → test
    split_of = {uniq[p]: ("train" if i < n_tr else "valid" if i < n_tr + n_va else "test") for i, p in enumerate(perm)}
    # ω and normalised ω: (VDD − 1.5)/0.15 and (T − 22.5)/12.5 (both roughly between −1 and +1)
    om = d["omega"]; omn = np.stack([(om[:, 0] - 1.5) / 0.15, (om[:, 1] - 22.5) / 12.5], axis=1)
    # conditioning of every simulation = 30 θ values followed by the 2 ω values (32 numbers)
    cond = np.concatenate([d["theta"], omn], axis=1).astype(np.float32)
    # input and output: every 10th point, of these the first 500
    vg1 = d["vg1"][:, ::STEP][:, :N_T]; vout = d["vout"][:, ::STEP][:, :N_T]
    # For every simulation
    for k, r in enumerate(idx):
        # part of its chip
        sp = split_of[keys[k]]
        # input = 32 conditioning values followed by the 500 vg1 values; output = the 500 vout values
        X[sp].append(np.concatenate([cond[k], vg1[k]])); Y[sp].append(vout[k])
        # row for split.csv: dataset, number in the raw data, chip key, type, part
        rows.append([name, r["n"], keys[k], r["typ"], sp])
    # number of simulations per part for this dataset
    cnt = {s: sum(1 for x in rows if x[0] == name and x[4] == s) for s in X}
    # feedback: number of chips and simulations per part
    print(f"{name}: {len(uniq)} Chips/Gruppen → {cnt}")
# Output folder 03_Cadence/datasets/<output name>, created if needed
D = ROOT / "datasets" / out_name; D.mkdir(parents=True, exist_ok=True)
# the dict that is saved
data = {}
# For every part (train, valid, test)
for s in X:
    # inputs as a tensor of shape (N, 532, 1) (unsqueeze(-1) adds a last axis of size 1)
    data[f"X_{s}"] = torch.tensor(np.array(X[s]), dtype=torch.float32).unsqueeze(-1)
    # outputs as a tensor of shape (N, 500)
    data[f"Y_{s}"] = torch.tensor(np.array(Y[s]), dtype=torch.float32)
# description of the format, saved in the same file
data["info"] = {"dt": 10e-6, "n_steps": N_T, "n_cond": 32, "cond_layout": "Präfix: 9 Process, 21 Mismatch, VDD_n, T_n",
                "omega_norm": "VDD_n = (VDD-1.5)/0.15, T_n = (T-22.5)/12.5", "split": "nach Chip, 70/20/10 je Datensatz, Seed 0",
                "quellen": names}
# Save the dict as a .ds file (torch format)
torch.save(data, D / f"{out_name}.ds")
# Write split.csv
with open(D / "split.csv", "w", newline="") as fo:
    # header line (column names in German) and one row per simulation
    w = csv.writer(fo); w.writerow(["datensatz", "n", "chip_schluessel", "typ", "split"]); w.writerows(rows)
# Feedback: shape of every tensor and the output file
print({k: tuple(v.shape) for k, v in data.items() if k != "info"}, "→", D / f"{out_name}.ds")
