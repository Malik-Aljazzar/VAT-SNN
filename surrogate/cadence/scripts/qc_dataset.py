"""Quality check of assembled datasets (checklist 29).

Usage: python qc_dataset.py <output folder> <Name> [<Name> ...]
Checks per dataset: completeness (expected = signals in meta.csv × chips), NaN/Inf, input = PWL file (sample),
amplitude ≤ VDD, coverage of the input ranges, share of non-firing cases and spike counts per type,
θ and ω distribution. Writes report.txt and qc.png to the output folder.
"""
# sys: command-line arguments and output; csv: CSV files
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
# print as UTF-8 so that θ, ω, … also work in the Windows console
sys.stdout.reconfigure(encoding="utf-8")

# ROOT = folder 03_Cadence (one level above the scripts folder)
ROOT = Path(__file__).resolve().parents[1]
# out = output folder (1st argument, created if needed); names = datasets to check (all further arguments)
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); names = sys.argv[2:]
# voltage bands of the input in V: below, near and above the thresholds
BANDS = [(0, 0.75), (0.75, 1.15), (1.15, 1.7)]
# all lines of the report (written to report.txt at the end)
lines = []
# say(): print a line and remember it for the report
def say(s=""):
    # print it and append it to lines
    print(s); lines.append(s)

# Spike count of every simulation = number of rising crossings of VDD/2
def spike_count(v, vdd):
    # s = True wherever the output is at or above VDD/2
    s = v >= vdd / 2                                   # v: (N, T), vdd: (N, 1)
    # count the steps from "below" to "at or above" along the time axis
    return np.sum(~s[:, :-1] & s[:, 1:], axis=-1)

# per dataset: the data for the joint plot at the end
summary = {}
# Check every dataset
for name in names:
    # D = dataset folder, S = stimulus folder
    D = ROOT / "datasets" / name; S = ROOT / "stimuli" / name
    # load the raw data
    d = np.load(D / f"{name}_raw.npz")
    # index rows (one per simulation)
    idx = list(csv.DictReader(open(D / "index.csv")))
    # input, output, θ and ω of all simulations
    vg1, vout, th, om = d["vg1"], d["vout"], d["theta"], d["omega"]
    # groups by number: {group number: row of groups.csv}
    groups = {r["group"]: r for r in csv.DictReader(open(S / "groups.csv"))}
    # number of jobs = number of rows in meta.csv
    n_jobs = sum(1 for _ in csv.DictReader(open(S / "meta.csv")))   # one job per signal in meta.csv
    # chips per group (numruns of the first group; the same for all groups)
    per = int(next(iter(groups.values()))["numruns"])
    # heading of this dataset in the report
    say(f"===== {name}")
    # completeness: simulations found vs. expected (jobs × chips)
    say(f"simulations: {len(idx)} of {n_jobs * per} expected ({n_jobs} jobs × {per} chips)")
    # number of invalid values (NaN or infinite) in input and output
    say(f"NaN/Inf: vg1 {int(np.sum(~np.isfinite(vg1)))}, vout {int(np.sum(~np.isfinite(vout)))}")
    # VDD of every simulation
    vdd = om[:, 0]
    # how far the maximum of vout lies above VDD (negative = below)
    over = np.max(vout, axis=1) - vdd
    # report the largest value and whether all stay below VDD + 20 mV
    say(f"Amplitude: max(vout) − VDD ≤ {over.max() * 1e3:.1f} mV (all ≤ VDD + 20 mV: {bool(np.all(over < 0.02))})")
    # input vs. PWL file (sample)
    # pick 100 random simulations (seed 0, each at most once)
    rng = np.random.default_rng(0); pick = rng.choice(len(idx), size=min(100, len(idx)), replace=False)
    # largest deviation of each sample
    dev = []
    # for every sample
    for k in pick:
        # read times and voltages of its PWL file
        t_p, v_p = np.loadtxt(S / idx[k]["signal"], unpack=True)
        # put the PWL signal onto the time grid and store the largest difference to the simulated vg1
        dev.append(np.max(np.abs(np.interp(d["t"], t_p, v_p) - vg1[k])))
    # report the largest deviation in mV
    say(f"vg1 vs. PWL file (100 samples): max. deviation {max(dev) * 1e3:.2f} mV")
    # coverage and firing per type
    # signal type of every simulation; spike count of every simulation
    types = np.array([r["type"] for r in idx]); sc = spike_count(vout, vdd[:, None])
    # table header: type, count, share per voltage band, share without spikes, spike count median (P10–P90)
    say(f"{'type':4s} {'n':>6s} " + " ".join(f"{f'{a:g}–{b:g} V':>11s}" for a, b in BANDS) + f" {'no spike':>13s} {'spikes median (P10–P90)':>24s}")
    # one table row per type
    for typ in "ABCD":
        # m = True for the simulations of this type
        m = types == typ
        # skip types that do not occur
        if not m.any():
            continue
        # share of the input values in each voltage band, in %
        frac = [np.mean((vg1[m] >= a) & (vg1[m] < b)) * 100 for a, b in BANDS]
        # 10th, 50th (median) and 90th percentile of the spike counts
        p10, p50, p90 = np.percentile(sc[m], [10, 50, 90])
        # print the row
        say(f"{typ:4s} {m.sum():6d} " + " ".join(f"{f:10.1f}%" for f in frac) + f" {np.mean(sc[m] == 0) * 100:12.1f}% {p50:12.0f} ({p10:.0f}–{p90:.0f})")
    # θ and ω
    # θ components that vary at all (standard deviation > 0)
    varied = np.std(th, axis=0) > 0
    # if there are any: report their number, mean and standard deviation (expected ≈ 0 and 1)
    if varied.any():
        say(f"θ: {varied.sum()} of 30 components vary; mean {th[:, varied].mean():+.3f}, σ {th[:, varied].std():.3f} (expected ≈ 0 / 1)")
    # range of VDD and T, and number of different ω values
    say(f"ω: VDD {om[:, 0].min():.3f}–{om[:, 0].max():.3f} V, T {om[:, 1].min():.1f}–{om[:, 1].max():.1f} °C, {len(np.unique(om, axis=0))} different values")
    # empty line
    say()
    # remember the data of this dataset for the plot
    summary[name] = (vg1, types, sc, om)

# plot: coverage of vg1, spike counts per type, ω
# colours
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
# figure with 3 plots side by side
fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
# every 50th input value of all datasets (enough for the histogram)
allv = np.concatenate([s[0].ravel()[::50] for s in summary.values()])
# left: histogram of the input voltages in 20 mV bins, axis label, title
ax[0].hist(allv, bins=np.arange(0, 1.71, 0.02), color=C[0]); ax[0].set_xlabel("vg1 (V)"); ax[0].set_title("input coverage (all)", loc="left", fontsize=10)
# for the band near the thresholds (0.75–1.15 V) …
for a, b in BANDS[1:2]:
    # … a grey background behind the bars
    ax[0].axvspan(a, b, color="#e5e4e0", zorder=0)
# types and spike counts of all datasets
types = np.concatenate([s[1] for s in summary.values()]); sc = np.concatenate([s[2] for s in summary.values()])
# middle: for every type (with its own colour)
for i, typ in enumerate("ABCD"):
    # m = True for the simulations of this type
    m = types == typ
    # if the type occurs: histogram of its spike counts as an outline
    if m.any():
        ax[1].hist(sc[m], bins=np.arange(0, 45, 1), histtype="step", lw=1.5, color=C[i], label=f"type {typ}")
# axis label, legend and title of the middle plot
ax[1].set_xlabel("spikes per simulation"); ax[1].legend(frameon=False, fontsize=8); ax[1].set_title("spike counts per type", loc="left", fontsize=10)
# ω of all simulations
om = np.concatenate([s[3] for s in summary.values()])
# right: scatter plot VDD vs. T with axis labels
ax[2].scatter(om[:, 0], om[:, 1], s=10, color=C[0]); ax[2].set_xlabel("VDD (V)"); ax[2].set_ylabel("T (°C)")
# title of the right plot
ax[2].set_title("ω per group", loc="left", fontsize=10)
# for every plot …
for a in ax:
    # … the upper and the right frame line …
    for s in ("top", "right"):
        # … are hidden
        a.spines[s].set_visible(False)
# arrange the plots and save the figure as qc.png
fig.tight_layout(); fig.savefig(out / "qc.png", dpi=100)
# write the report lines to report.txt
(out / "report.txt").write_text("\n".join(lines), encoding="utf-8")
# print the path of the plot
print(out / "qc.png")
