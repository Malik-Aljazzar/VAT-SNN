"""Generate input signals Vg1(t) as PWL files for `vpwlf` ([Plan 5.1], checklist 17/19/24).

Usage:
  python make_stimuli.py <target folder> test
      → one example each for types A, B, C
  python make_stimuli.py <target folder> cascade <count> <seed> <pool folder> [<pool folder> ...]
      → type D from real vout traces (CSV with column "vout" or OCEAN text), plus meta.csv
Format per line: "<t in s> <V in V>". All signals start at 0 V, length 5 ms, range 0–1.65 V.
"""
# sys: command-line arguments; csv: read and write CSV files; re: regular expressions (text patterns)
import sys, csv, re
# Path: convenient handling of file and folder paths
from pathlib import Path
# numpy: arrays and maths
import numpy as np

# Times in seconds: signal length 5 ms, grid step 1 µs, signal switches on at 10 µs, edges take 1 µs
T_END, DT, T_ON, RISE = 5e-3, 1e-6, 10e-6, 1e-6     # length, grid step, switch-on time, edge time
# Highest allowed input voltage in V
V_MAX = 1.65
# Time grid 0, 1 µs, 2 µs, … 5 ms (5001 points; "+ DT / 2" makes sure that 5 ms itself is included)
GRID = np.arange(0, T_END + DT / 2, DT)

def write(path, t, v):
    """Write a signal as a PWL file for Spectre: one line "<t> <v>" per point, Unix line endings.

    Args:
        path (Path): target file, e.g. stimuli/ds_all/g0/A_003.pwl
        t (array): times in s, rising, e.g. [0, 10e-6, 11e-6, 5e-3]
        v (array): voltages in V, same length as t; values outside 0 … V_MAX (1.65 V) are clipped
    """
    # Limit the voltages to 0 … V_MAX
    v = np.clip(v, 0.0, V_MAX)
    # Open the file for writing (closed automatically at the end of the block)
    with open(path, "w", newline="\n") as f:                 # Unix line endings for the server
        # Go through times and voltages in pairs
        for a, b in zip(t, v):
            # One line: time with 9, voltage with 6 significant digits
            f.write(f"{a:.9g} {b:.6g}\n")

def ramp(t):
    """Switch-on ramp 0 → 1 between T_ON and T_ON + 100 µs (start at 0 V).

    A signal is multiplied by it so that it starts at 0 V and rises smoothly instead of jumping.

    Args:
        t (array): times in s, usually GRID
    Returns:
        array of the same length: 0 before T_ON (10 µs), rising linearly to 1 until 110 µs, then 1
    """
    # (t − T_ON) / 100 µs rises from 0 to 1 within 100 µs after T_ON; clip keeps it at 0 before and at 1 after
    return np.clip((t - T_ON) / 100e-6, 0, 1)

def typ_a(level):
    """Constant: 0 V until T_ON, then a step to level.

    Args:
        level (float): input voltage in V, e.g. 1.2
    Returns:
        (t, v): 4 corner points, e.g. t = [0, 10e-6, 11e-6, 5e-3], v = [0, 0, 1.2, 1.2]
    """
    # Four corner points: 0 V at t = 0 and at T_ON, the level after the edge (T_ON + RISE) and at the end
    return np.array([0, T_ON, T_ON + RISE, T_END]), np.array([0, 0, level, level])

def typ_b(levels, holds):
    """Steps: sequence of levels with hold times (s), edges of RISE; first level from T_ON.

    Steps that no longer fit into the 5 ms are dropped; if the steps end earlier,
    the last level is held until 5 ms.

    Args:
        levels (list of float): voltage of each step in V, e.g. [1.2, 0.85, 1.05]
        holds (list of float): hold time of each step in s, same length, e.g. [1e-3, 0.8e-3, 1.2e-3]
    Returns:
        (t, v): corner points, 2 per step (each edge takes RISE = 1 µs)
    """
    # Start: 0 V at t = 0 and at T_ON; now = current time (end of the last step so far)
    t, v, now = [0, T_ON], [0, 0], T_ON
    # Go through the levels together with their hold times
    for lvl, h in zip(levels, holds):
        # Stop if no further edge fits before the end
        if now + RISE >= T_END:                               # edge would lie beyond the end
            break
        # Edge: RISE later the signal has reached the new level
        t += [now + RISE]; v += [lvl]
        # Hold the level for h seconds, but at most until the end
        now = min(now + h, T_END)
        # Point at the end of the hold time (same level)
        t += [now]; v += [lvl]
        # Stop when the end of the signal is reached
        if now >= T_END:
            break
    # If the steps end before 5 ms: hold the last level until the end
    if t[-1] < T_END:
        t += [T_END]; v += [v[-1]]
    # Return times and voltages as numpy arrays
    return np.array(t), np.array(v)

def typ_c(offset, comps):
    """Sum of sines: comps = [(amplitude, frequency, phase)], switch-on ramp 0 → signal over 100 µs.

    v(t) = (offset + Σ a·sin(2π·f·t + p)) · ramp(t)

    Args:
        offset (float): mean voltage in V, e.g. 0.95
        comps (list of tuples): one (amplitude in V, frequency in Hz, phase in rad) per sine,
            e.g. [(0.25, 400, 0.0), (0.08, 2300, 1.0)]
    Returns:
        (t, v): t = GRID (5001 points, 1 µs apart), v = the signal at these times
    """
    # Offset plus all sine components a·sin(2π·f·t + p), evaluated on the 1 µs grid
    v = offset + sum(a * np.sin(2 * np.pi * f * GRID + p) for a, f, p in comps)
    # Multiply by the switch-on ramp (so the signal starts at 0 V) and return it together with the grid
    return GRID, v * ramp(GRID)

def load_pool(folders, vdd=1.5, types=None):
    """Load vout traces (with at least 2 spikes) from CSV (column "vout") or OCEAN text (3rd column).

    Used for the cascade signals (type D): their inputs are real neuron outputs.

    Args:
        folders (list of paths): folders with the traces, e.g. [exports/ds_all/sims/g0]
        vdd (float): supply voltage in V; a spike = rising crossing of vdd/2
        types (tuple of str or None): only files whose signal type (name before the first "_")
            is in it, e.g. ("A", "B", "C"); None = all files
    Returns:
        (pool, names): pool = list of traces on GRID (5001 values in V each),
            names = "<folder>/<file name>" of each trace, e.g. "g0/A_003_i5"
    """
    # pool = list of the traces (each on the 1 µs grid), names = "<folder>/<file name>" of each trace
    pool, names = [], []
    # Go through the given folders (as Path objects)
    for d in map(Path, folders):
        # Go through all CSV files and then all text files of the folder, each sorted by name
        for p in sorted(d.glob("*.csv")) + sorted(d.glob("*.txt")):
            # If types is given: skip files of other signal types (file name e.g. "A_003_i5" → type "A")
            if types is not None and p.stem.split("_")[0] not in types:
                continue
            # CSV file (written by gen_job.sh / psf_to_csv.py):
            if p.suffix == ".csv":
                # read all rows as dicts {column name: value}
                r = list(csv.DictReader(open(p)))
                # skip empty files and files without a column "vout"
                if not r or "vout" not in r[0]:
                    continue
                # times and vout values as numpy arrays
                t = np.array([float(x["t"]) for x in r]); v = np.array([float(x["vout"]) for x in r])
            # otherwise: OCEAN text export
            else:
                # keep only lines that start with a number like 1.2e-05 (the data lines), split at whitespace
                rows = [l.split() for l in open(p) if re.match(r"\s*[0-9.]+e[+-]\d+", l)]
                # as a table of numbers; 1st column = time, 3rd column = vout
                a = np.array(rows, dtype=float); t, v = a[:, 0], a[:, 2]
            # Put the trace onto the 1 µs grid (linear interpolation)
            v = np.interp(GRID, t, v)
            # Count the rising crossings of VDD/2 (= spikes); keep the trace only if there are at least 2
            if np.sum((v[:-1] < vdd / 2) & (v[1:] >= vdd / 2)) >= 2:
                # store the trace and its name
                pool.append(v); names.append(f"{d.name}/{p.stem}")
    # Return the traces and their names
    return pool, names

def typ_d(rng, pool, vdd=1.5, k_range=(2, 8), p_inv=0.3, lo=0.75, hi=1.15, min_frac=0.2, tries=200):
    """Cascade: Vg1 = w_b·VDD + Σ w_j·x_j + Σ w_k·(VDD − x_k) + w_0·0, weights ≥ 0 summing to 1.
    x = real vout traces, randomly delayed by 0–1 ms; kept if ≥ min_frac of the time lies in [lo, hi].

    Imitates the input of a neuron in a deeper layer: the crossbar mixes the outputs of earlier
    neurons (some of them through an inverter), a bias line at VDD and a line at ground (0 V).

    Args:
        rng (np.random.Generator): random number generator, e.g. np.random.default_rng(seed)
        pool (list of arrays): vout traces on GRID, from load_pool
        vdd (float): supply voltage in V (bias line and inverter VDD − x)
        k_range (tuple of int): smallest and largest number of inputs, e.g. (2, 8)
        p_inv (float): probability that an input goes through an inverter
        lo, hi (float): voltage band near the thresholds in V
        min_frac (float): minimum share of the time (after 0.2 ms) inside [lo, hi]
        tries (int): number of attempts before giving up
    Returns:
        (t, v, meta): t = GRID, v = the signal, meta = dict of the drawn parameters for meta.csv
            (k, inputs = positions in pool, inverted 0/1, shift_us, w_inputs, w_bias, w_ground,
            frac_near_threshold)
    Raises:
        RuntimeError: if no attempt reaches min_frac
    """
    # Up to `tries` attempts to draw a suitable signal
    for _ in range(tries):
        # Number of inputs k: random whole number from 2 to 8
        k = rng.integers(k_range[0], k_range[1] + 1)
        # Pick k different traces from the pool at random (their positions in the pool)
        idx = rng.choice(len(pool), size=k, replace=False)
        # For each input decide at random (probability p_inv) whether it goes through an inverter (VDD − x)
        inv = rng.random(k) < p_inv
        # Random delay of each input between 0 and 1 ms
        shift = rng.uniform(0, 1e-3, k)
        # k + 2 random weights ≥ 0 that add up to 1 (Dirichlet distribution)
        w = rng.dirichlet(np.ones(k + 2))                       # k inputs, bias, ground
        # Start with the bias part: weight w[k] times VDD, constant over time
        v = w[k] * vdd * np.ones_like(GRID)
        # Add each input
        for j in range(k):
            # trace j delayed by shift[j] (before it starts: its first value)
            x = np.interp(GRID - shift[j], GRID, pool[idx[j]], left=pool[idx[j]][0])
            # add it with its weight, inverted (VDD − x) or as it is
            v += w[j] * (vdd - x if inv[j] else x)
        # Multiply by the switch-on ramp (start at 0 V); the ground weight w[k + 1] adds nothing (it multiplies 0 V)
        v *= ramp(GRID)
        # Share of the time (after the first 0.2 ms) in which the signal lies between lo and hi (near the thresholds)
        frac = np.mean((v[GRID > 0.2e-3] >= lo) & (v[GRID > 0.2e-3] <= hi))
        # Accept the signal if this share is large enough
        if frac >= min_frac:
            # Parameters of the signal for meta.csv (numbers rounded and turned into plain Python types)
            meta = {"k": int(k), "inputs": idx.tolist(), "inverted": inv.astype(int).tolist(),
                    "shift_us": np.round(shift * 1e6).astype(int).tolist(), "w_inputs": np.round(w[:k], 4).tolist(),
                    "w_bias": round(float(w[k]), 4), "w_ground": round(float(w[k + 1]), 4), "frac_near_threshold": round(float(frac), 3)}
            # Return grid, signal and parameters
            return GRID, v, meta
    # No attempt was good enough: stop with an error
    raise RuntimeError("no suitable cascade signal found")

# Only when this file is run directly (not when gen_dataset.py imports it):
if __name__ == "__main__":
    # Target folder = 1st argument; create it if needed
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    # Mode = 2nd argument, "test" if none is given
    mode = sys.argv[2] if len(sys.argv) > 2 else "test"
    # Mode "test": write one example each of types A, B and C
    if mode == "test":
        # A: constant 1.2 V
        write(out / "A_1v20.pwl", *typ_a(1.20))
        # B: five steps with the given levels (V) and hold times (s)
        write(out / "B_steps.pwl", *typ_b([1.2, 0.85, 1.05, 0.6, 1.4], [1e-3, 0.8e-3, 1.2e-3, 0.5e-3, 2e-3]))
        # C: offset 0.95 V plus two sines (0.25 V at 400 Hz, 0.08 V at 2300 Hz)
        write(out / "C_sine.pwl", *typ_c(0.95, [(0.25, 400, 0.0), (0.08, 2300, 1.0)]))
    # Mode "cascade": type D signals from the vout traces in the given folders
    elif mode == "cascade":
        # number of signals, seed and pool folders from the arguments
        n, seed, folders = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5:]
        # random number generator with this seed (same seed → same signals)
        rng = np.random.default_rng(seed)
        # load the vout traces (default VDD 1.5 V, all signal types)
        pool, names = load_pool(folders)
        # feedback: size of the pool and its folders
        print(f"Pool: {len(pool)} vout traces from {', '.join(Path(f).name for f in folders)}")
        # open meta.csv for writing
        with open(out / "meta.csv", "w", newline="") as fm:
            # CSV writer for this file
            wr = csv.writer(fm)
            # header line
            wr.writerow(["file", "type", "k", "inputs", "inverted", "shift_us", "w_inputs", "w_bias", "w_ground", "frac_0.75_1.15V"])
            # n signals
            for i in range(n):
                # draw one cascade signal
                t, v, m = typ_d(rng, pool)
                # file name D_000.pwl, D_001.pwl, …; write the signal as a PWL file
                f = f"D_{i:03d}.pwl"; write(out / f, t, v)
                # one row with its parameters in meta.csv (lists joined with ";")
                wr.writerow([f, "D", m["k"], ";".join(names[j] for j in m["inputs"]), ";".join(map(str, m["inverted"])),
                             ";".join(map(str, m["shift_us"])), ";".join(map(str, m["w_inputs"])), m["w_bias"], m["w_ground"],
                             m["frac_near_threshold"]])
    # Feedback for every PWL file in the target folder …
    for p in sorted(out.glob("*.pwl")):
        # … its name and number of lines (sum(1 for _ in open(p)) counts the lines)
        print(p.name, sum(1 for _ in open(p)), "lines")
