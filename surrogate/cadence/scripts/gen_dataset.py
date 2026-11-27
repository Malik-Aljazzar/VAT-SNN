"""Generate the surrogate dataset – local part (checklist 25/28). Server part: gen_run.sh / gen_job.sh.

Workflow (Name = dataset, e.g. ds_all):
  1. python gen_dataset.py plan <Name> <groups> <chips/group> <MC seed> <signal seed> [A B C]
       → 03_Cadence/stimuli/<Name>/g<k>/*.pwl, jobs1.txt, groups.csv, meta.csv   (then upload_stimuli.sh <Name>)
     Server: run_remote.sh gen_run.sh <Name> jobs1.txt <parallel>   → fetch_tar.sh <Name>
  2. python gen_dataset.py cascade <Name> <D per group> <seed>
       → type D signals per group from that group's own A/B/C vout traces, jobs2.txt  (upload, gen_run.sh … jobs2.txt, fetch)
  3. python gen_dataset.py assemble <Name>
       → 03_Cadence/datasets/<Name>/<Name>_raw.npz (vg1, vout on the 1 µs grid, θ, ω, metadata) + index.csv

Variation: always process + mismatch (Spectre variations=all). ω = (VDD, T) per group, uniform
in 1.35–1.65 V × 10–35 °C. Catalogue and parameter ranges: Plan 5.1.
"""
# sys: command-line arguments; csv: CSV files; json: store parameters as text; re: regular expressions
import sys, csv, json, re
# Path: convenient handling of file and folder paths
from pathlib import Path
# numpy: arrays and maths
import numpy as np
# Let Python also look for modules in the folder of this script (needed for make_stimuli.py)
sys.path.insert(0, str(Path(__file__).parent))
# Functions that write and generate the signals, and the 1 µs time grid
from make_stimuli import write, typ_a, typ_b, typ_c, typ_d, load_pool, GRID

# ROOT = folder 03_Cadence (one level above the scripts folder)
ROOT = Path(__file__).resolve().parents[1]
# Ranges of ω, drawn uniformly per group: VDD in V, temperature in °C
VDD_RANGE, T_RANGE = (1.35, 1.65), (10.0, 35.0)
# Input levels in V: LO … HI = dense range around the thresholds, VMAX = highest level
LO, HI, VMAX = 0.75, 1.15, 1.65                       # dense range around the thresholds, upper limit
# Names of the 9 process parameters that form θ_process, in this order
PROC = ["norm_vfbo", "norm_vfbl", "norm_uo", "norm_xcoro", "norm_xcorl", "norm_lovo",
        "dresscale", "dw_resrand1", "dcapscale"]       # 9 process values with σ ≠ 0 (Plan 3.1)
# Number of mismatch values that form θ_mismatch
N_MIS = 21                                             # mismatch values (order as in compactmismatchparam)

def level(rng):
    """Level: half in the dense range around the thresholds, half over the whole range."""
    # With probability 0.5 a value in LO … HI, otherwise a value in 0 … VMAX
    return rng.uniform(LO, HI) if rng.random() < 0.5 else rng.uniform(0, VMAX)

# Type A: returns the signal (t, v) and its parameters for meta.csv
def make_a(rng):
    # draw one level, build the constant signal; parameter = the level rounded to 4 digits
    v = level(rng); return typ_a(v), {"level": round(v, 4)}

# Type B: 3–8 steps with random levels and hold times
def make_b(rng):
    # n = number of steps (3 … 8); lv = one level per step; hd = hold time per step between 0.2 and 2 ms
    n = int(rng.integers(3, 9)); lv = [level(rng) for _ in range(n)]; hd = list(rng.uniform(0.2e-3, 2e-3, n))
    # build the step signal; parameters: levels and hold times in ms (rounded)
    return typ_b(lv, hd), {"levels": [round(x, 4) for x in lv], "holds_ms": [round(h * 1e3, 3) for h in hd]}

# Type C: an offset plus 1–3 sines
def make_c(rng):
    # off = offset between 0.6 and 1.3 V; n = number of sines (1 … 3)
    off = rng.uniform(0.6, 1.3); n = int(rng.integers(1, 4))
    # per sine: amplitude 0.05–0.5 V divided by √n, frequency spread evenly on a log scale between 50 Hz and 5 kHz, phase 0–2π
    comps = [(rng.uniform(0.05, 0.5) / n ** 0.5, float(np.exp(rng.uniform(np.log(50), np.log(5e3)))), rng.uniform(0, 2 * np.pi))
             for _ in range(n)]
    # build the sine signal; parameters: offset and (amplitude, frequency, phase) of each sine (rounded)
    return typ_c(off, comps), {"offset": round(off, 4), "comps": [[round(a, 4), round(f, 1), round(p, 3)] for a, f, p in comps]}

# Generator function for each signal type
MAKERS = {"A": make_a, "B": make_b, "C": make_c}
# ("A", "B", "C") = the keys of MAKERS
POOL_TYPES = tuple(MAKERS)                             # cascade inputs only from stage-1 signals A/B/C

# Stage 1: create the chip groups, the signals A/B/C and the job file jobs1.txt
def plan(name, n_groups, per_group, mc_seed, stim_seed, counts):
    # Random number generator for ω and signals (same seed → same dataset)
    rng = np.random.default_rng(stim_seed)
    # S = stimulus folder 03_Cadence/stimuli/<Name>; create it if needed
    S = ROOT / "stimuli" / name; S.mkdir(parents=True, exist_ok=True)
    # Collected: one row per group, one row of parameters per signal, one job line per signal
    groups, metas, jobs = [], [], []
    # For every group g = 0, 1, …
    for g in range(n_groups):
        # first chip number of the group (group 0: chips 1 …, group 1: chips per_group + 1 …)
        first = 1 + g * per_group
        # draw ω of the group: VDD (rounded to 4 digits) and temperature (2 digits)
        vdd, temp = round(rng.uniform(*VDD_RANGE), 4), round(rng.uniform(*T_RANGE), 2)
        # remember the group: number, first chip, number of chips, VDD, T, Monte Carlo seed
        groups.append([g, first, per_group, vdd, temp, mc_seed])
        # create the subfolder g<g> for the signals of this group
        (S / f"g{g}").mkdir(exist_ok=True)
        # for every signal type and its count (e.g. "A", 7)
        for typ, cnt in counts.items():
            # cnt signals of this type
            for k in range(cnt):
                # draw a signal of this type: (t, v) = the signal, par = its parameters
                (t, v), par = MAKERS[typ](rng)
                # file name e.g. g0/A_003.pwl; write the signal as a PWL file
                f = f"g{g}/{typ}_{k:03d}.pwl"; write(S / f, t, v)
                # row for meta.csv: file, group, type, parameters as JSON text
                metas.append([f, g, typ, json.dumps(par)])
                # job line for gen_job.sh: group, firstrun, numruns, VDD, T, seed, signal file
                jobs.append(f"{g} {first} {per_group} {vdd} {temp} {mc_seed} {f}")
    # Write groups.csv
    with open(S / "groups.csv", "w", newline="") as fo:
        # header line and one row per group
        w = csv.writer(fo); w.writerow(["group", "firstrun", "numruns", "vdd", "temp", "mc_seed"]); w.writerows(groups)
    # Write meta.csv
    with open(S / "meta.csv", "w", newline="") as fo:
        # header line and one row per signal
        w = csv.writer(fo); w.writerow(["file", "group", "type", "parameters"]); w.writerows(metas)
    # Write jobs1.txt with Unix line endings (it is read on the server)
    with open(S / "jobs_base_stimuli.txt", "w", newline="\n") as fo:
        # one job per line
        fo.write("\n".join(jobs) + "\n")
    # Feedback: groups, chips, jobs and simulations (= jobs × chips per group)
    print(f"{name}: {n_groups} groups × {per_group} chips, {len(jobs)} jobs (stage 1) = {len(jobs) * per_group} simulations")

# Stage 2: type D signals per group from that group's own stage-1 vout traces, job file jobs2.txt
def cascade(name, n_d, seed):
    # Random number generator for the cascade signals
    rng = np.random.default_rng(seed)
    # S = stimulus folder, E = fetched results of stage 1 (03_Cadence/exports/<Name>/sims)
    S = ROOT / "stimuli" / name; E = ROOT / "exports" / name / "sims"
    # read the groups from groups.csv (one dict per row)
    groups = list(csv.DictReader(open(S / "groups.csv")))
    # collected: parameters and job lines of the new signals
    metas, jobs = [], []
    # For every group
    for gr in groups:
        # group number and its VDD
        g, vdd = int(gr["group"]), float(gr["vdd"])
        # load the vout traces of this group (only types A/B/C, at least 2 spikes) as the pool
        pool, names = load_pool([E / f"g{g}"], vdd=vdd, types=POOL_TYPES)
        # n_d cascade signals for this group
        for k in range(n_d):
            # draw a cascade signal from the pool (at the VDD of the group)
            t, v, m = typ_d(rng, pool, vdd=vdd)
            # file name e.g. g0/D_003.pwl; write the signal as a PWL file
            f = f"g{g}/D_{k:03d}.pwl"; write(S / f, t, v)
            # replace the positions of the inputs in the pool by their names (traceable in meta.csv)
            m["inputs"] = [names[j] for j in m["inputs"]]
            # row for meta.csv
            metas.append([f, g, "D", json.dumps(m)])
            # job line with the values of the group
            jobs.append(f"{g} {gr['firstrun']} {gr['numruns']} {gr['vdd']} {gr['temp']} {gr['mc_seed']} {f}")
        # feedback per group: size of the pool and number of new signals
        print(f"g{g}: pool {len(pool)} traces → {n_d} cascade signals")
    # Append the new signals to meta.csv ("a" = append instead of overwrite)
    with open(S / "meta.csv", "a", newline="") as fo:
        # one row per new signal
        csv.writer(fo).writerows(metas)
    # Write jobs2.txt with Unix line endings
    with open(S / "jobs_cascade.txt", "w", newline="\n") as fo:
        # one job per line
        fo.write("\n".join(jobs) + "\n")
    # Feedback: number of jobs
    print(f"{len(jobs)} jobs (stage 2)")

def read_theta(th, g, stim):
    """θ per chip from processData (9 relevant columns) and mismatchData (21 values); missing → 0."""
    # empty dict (not used any further)
    out = {}
    # paths of the θ files of this group and signal: names and values of the process parameters …
    pp, pd = th / f"g{g}_{stim}_processParam", th / f"g{g}_{stim}_processData"
    # … and the mismatch values
    md = th / f"g{g}_{stim}_mismatchData"
    # proc = process values, one list per chip (in chip order)
    proc = []
    # only if the process file exists:
    if pd.exists():
        # names of all process parameters (last word of every non-empty line that is not a comment)
        names = [l.split()[-1] for l in open(pp) if l.strip() and not l.startswith("#")]
        # column position of each of the 9 wanted parameters
        idx = [names.index(p) for p in PROC]
        # for every chip (one non-empty line each) the values in these 9 columns
        proc = [[float(r.split()[i]) for i in idx] for r in open(pd) if r.strip()]
    # mis = {chip number: 21 mismatch values}, cur = chip number of the current block
    mis, cur = {}, None
    # only if the mismatch file exists:
    if md.exists():
        # go through the file line by line
        for l in open(md):
            # the line without spaces and line break at the start and end
            t = l.strip()
            # a line "#<number>" starts the block of chip <number>
            if t.startswith("#"):
                cur = int(t[1:])
            # a non-empty data line: the mismatch values of this chip
            elif t:
                mis[cur] = [float(x) for x in t.split()]
    # Return the process values (list in chip order) and the mismatch values (by chip number)
    return proc, mis

# Merge all simulations of a dataset into one npz file plus index.csv
def assemble(name):
    # S = stimulus folder, E = fetched results, D = output folder 03_Cadence/datasets/<Name>
    S = ROOT / "stimuli" / name; E = ROOT / "exports" / name; D = ROOT / "datasets" / name
    # create the output folder if needed
    D.mkdir(parents=True, exist_ok=True)
    # groups by number: {group number: row of groups.csv}
    groups = {int(r["group"]): r for r in csv.DictReader(open(S / "groups.csv"))}
    # signals by file name: {signal file: row of meta.csv}
    meta = {r["file"]: r for r in csv.DictReader(open(S / "meta.csv"))}
    # collected: inputs, outputs, θ, ω and index rows of all simulations
    VG1, VOUT, TH, OM, rows = [], [], [], [], []
    # θ of every chip number seen so far (for the consistency check)
    theta_seen = {}
    # For every signal in meta.csv
    for f, m in meta.items():
        # group number, its row, and the signal name without folder and ending (e.g. A_003)
        g = int(m["group"]); gr = groups[g]; stim = Path(f).stem
        # first chip number of the group
        first = int(gr["firstrun"])
        # θ values of all chips of this group for this signal
        proc, mis = read_theta(E / "theta", g, stim)
        # for every result file of this signal (one per chip, e.g. A_003_i5.csv), sorted by name
        for p in sorted((E / "sims" / f"g{g}").glob(f"{stim}_i*.csv")):
            # chip number from the file name (the digits after "_i")
            chip = int(re.search(r"_i(\d+)\.csv$", p.name).group(1))
            # read the CSV as a table with the named columns t, vg1, vout
            a = np.genfromtxt(p, delimiter=",", names=True)
            # files with fewer than 10 rows are broken: report and skip them
            if len(a) < 10:
                print("empty:", p); continue
            # put input and output onto the exact 1 µs grid (linear interpolation)
            vg1, vout = np.interp(GRID, a["t"], a["vg1"]), np.interp(GRID, a["t"], a["vout"])
            # θ vector of 9 process + 21 mismatch values, filled with zeros first
            th = np.zeros(len(PROC) + N_MIS)
            # if there are process values: take those of this chip (position chip − first)
            if proc:
                th[:len(PROC)] = proc[chip - first]
            # if there are mismatch values for this chip: put them after the process values
            if chip in mis:
                th[len(PROC):] = mis[chip]
            # key for the check = chip number
            key = chip
            # if this chip was seen before with different θ: stop with an error
            if key in theta_seen and not np.allclose(theta_seen[key], th):
                raise RuntimeError(f"θ of chip {chip} differs between signals ({f})")
            # remember the θ of this chip
            theta_seen[key] = th
            # store input, output and θ as 32-bit numbers
            VG1.append(vg1.astype(np.float32)); VOUT.append(vout.astype(np.float32)); TH.append(th.astype(np.float32))
            # store ω = (VDD, T) of the group
            OM.append([float(gr["vdd"]), float(gr["temp"])])
            # index row: running number, chip, group, signal file, type, VDD, T
            rows.append([len(rows), chip, g, f, m["type"], gr["vdd"], gr["temp"]])
    # Save everything compressed in <Name>_raw.npz: one array per field (chip and group taken from the index rows)
    np.savez_compressed(D / f"{name}_raw.npz", vg1=np.array(VG1), vout=np.array(VOUT), theta=np.array(TH),
                        omega=np.array(OM, dtype=np.float32), chip=np.array([r[1] for r in rows]),
                        group=np.array([r[2] for r in rows]), t=GRID.astype(np.float32),
                        theta_names=np.array(PROC + [f"mis_{i}" for i in range(N_MIS)]))
    # Write index.csv
    with open(D / "index.csv", "w", newline="") as fo:
        # header line and one row per simulation
        w = csv.writer(fo); w.writerow(["n", "chip", "group", "signal", "type", "vdd", "temp"]); w.writerows(rows)
    # number of simulations per signal type
    types = {t: sum(1 for r in rows if r[4] == t) for t in "ABCD"}
    # Feedback: simulations, chips, types and output file
    print(f"{name}: {len(rows)} simulations, {len(theta_seen)} chips, types {types} → {D / (name + '_raw.npz')}")

# Only when this file is run directly:
if __name__ == "__main__":
    # command (plan / cascade / assemble) and dataset name from the arguments
    cmd, name = sys.argv[1], sys.argv[2]
    # plan: arguments groups, chips per group, MC seed, signal seed, optionally the counts of A, B, C
    if cmd == "plan":
        # read the four numbers
        n_g, per, mcs, sts = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
        # counts of A, B, C from arguments 7–9, otherwise 5 / 3 / 3
        cnt = [int(x) for x in sys.argv[7:10]] if len(sys.argv) >= 10 else [5, 3, 3]
        # run stage 1; dict(zip("ABC", cnt)) gives {"A": …, "B": …, "C": …}
        plan(name, n_g, per, mcs, sts, dict(zip("ABC", cnt)))
    # cascade: arguments D signals per group and seed
    elif cmd == "cascade":
        # run stage 2
        cascade(name, int(sys.argv[3]), int(sys.argv[4]))
    # assemble: no further arguments
    elif cmd == "assemble":
        # merge everything
        assemble(name)
