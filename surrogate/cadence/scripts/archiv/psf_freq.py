"""freq und amp aus Spectre-psfascii-Ausgaben (läuft auf dem Server, nur Standardbibliothek).

Nutzung: python3 psf_freq.py <raw-Ordner> <Corner-Name> <VDD> <T> <VG1,VG1,...> <Ausgabe.csv>
Erwartet <raw>/mc1_separate/<iter>/<k>_tran.tran.tran (Spectre: savedatainseparatedir, savefamilyplots, wfseparation).
Kennzahlen wie in ADE XL: Fenster 1–5 ms, freq = 0, wenn ymax <= VDD/2, sonst mittlere Frequenz
aus steigenden Durchgängen durch die Mitte zwischen Minimum und Maximum; amp = ymax.
"""
import sys, os, re, glob

raw, corner, vdd, temp, vg1s, out = sys.argv[1:7]
vdd = float(vdd); vgs = [float(x) for x in vg1s.split(",")]

def read(path):
    t, v, cur, inval = [], [], None, False
    with open(path) as f:
        for line in f:
            if not inval:
                inval = line.startswith("VALUE")
                continue
            p = line.split()
            if not p or p[0] == "END":
                continue
            if p[0] == '"time"':
                cur = float(p[1])
            elif p[0] == '"vout"' and cur is not None:
                t.append(cur); v.append(float(p[1]))
    return t, v

def measure(t, v):
    w = [(a, b) for a, b in zip(t, v) if 1e-3 <= a <= 5e-3]
    ys = [b for _, b in w]
    ymax, ymin = max(ys), min(ys)
    if ymax <= vdd / 2:
        return 0.0, ymax
    mid = (ymax + ymin) / 2
    ups = [w[i][0] + (mid - w[i][1]) * (w[i + 1][0] - w[i][0]) / (w[i + 1][1] - w[i][1])
           for i in range(len(w) - 1) if w[i][1] < mid <= w[i + 1][1]]
    f = (len(ups) - 1) / (ups[-1] - ups[0]) if len(ups) >= 2 else 0.0
    return f, ymax

files = glob.glob(os.path.join(raw, "mc1_separate", "*", "*_tran.tran.tran"))
rows = []
for p in files:
    m = re.search(r"mc1_separate[/\\](\d+)[/\\](\d+)_tran\.tran\.tran$", p)
    it, k = int(m.group(1)), int(m.group(2))
    f, a = measure(*read(p))
    rows.append((it, k, f, a))
rows.sort()
with open(out, "w") as fo:
    fo.write("Point,Corner,VDD,VG1,mc_iteration,temperature,freq,amp\n")
    for it, k, f, a in rows:
        fo.write(f"{k + 1},{corner}_{k},{vdd:g},{vgs[k]:g},{it},{temp},{f:.6g},{a:.6g}\n")
print(f"{corner}: {len(rows)} Simulationen ausgewertet")
