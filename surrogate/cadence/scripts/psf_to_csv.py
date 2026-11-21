"""psfascii transient → CSV (runs on the server, standard library only).

Usage: python3 psf_to_csv.py <tran.tran.tran> <output.csv> <signal> [<signal> ...]
Signal names as in the psf file, e.g. vg1 vout neuron0.vcin. Columns: t, then the signals.
"""
# sys gives access to the command-line arguments
import sys

# src = Spectre result file (psfascii), out = CSV file to write, sigs = list of the signal names to keep
src, out, sigs = sys.argv[1], sys.argv[2], sys.argv[3:]
# rows = one dict per time point, cur = dict of the current time point, inval = already inside the VALUE section?
rows, cur, inval = [], None, False
# Open the Spectre result file for reading (it is closed automatically at the end of the block)
with open(src) as f:
    # Go through the file line by line
    for line in f:
        # As long as the VALUE section (the actual data) has not started yet …
        if not inval:
            # … check whether this line starts it (all lines before it are header information)
            inval = line.startswith("VALUE")
            # skip this line in any case
            continue
        # Split the line at whitespace, e.g. ['"time"', '1e-06'] or ['"vout"', '0.12']
        p = line.split()
        # Skip empty lines and the closing "END" line
        if not p or p[0] == "END":
            continue
        # Name of the value in this line, without the quotation marks
        name = p[0].strip('"')
        # A "time" line starts a new time point: new dict with the time t, appended to rows
        if name == "time":
            cur = {"t": float(p[1])}; rows.append(cur)
        # A line of a wanted signal (and a time point exists already): store its value under the signal name
        elif name in sigs and cur is not None:
            cur[name] = float(p[1])
# Open the CSV file for writing
with open(out, "w") as fo:
    # Header line: t, then the signal names, separated by commas
    fo.write(",".join(["t"] + sigs) + "\n")
    # For every time point …
    for r in rows:
        # … but only if all wanted signals have a value there …
        if all(s in r for s in sigs):
            # … write one line: time and signal values with 6 significant digits, separated by commas
            fo.write(",".join(f"{r[k]:.6g}" for k in ["t"] + sigs) + "\n")
# Feedback: name of the CSV file and number of time points read
print(f"{out}: {len(rows)} Zeitpunkte")
