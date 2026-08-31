"""Dump candidate numbers for every labelled frame, so a rule can be chosen
from the separation instead of from a hunch."""
import os, sys, json
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

def numbers(bgr):
    bgr = sc.to_working_size(bgr)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gi = g.astype(np.int16)
    h, w = g.shape
    d = {}
    d["ties"] = sc.screen_fraction(bgr)[0]
    hor = np.abs(np.diff(gi, axis=1)) > 32          # a vertical ink edge
    ver = np.abs(np.diff(gi, axis=0)) > 32          # a horizontal ink edge
    d["step"] = float((hor.mean() + ver.mean()) / 2)
    # LONG STRAIGHT EDGES: a window border, a divider, a menu bar. Runs of
    # touching edge pixels along one row or one column.
    def longest_runs(mask, axis, least):
        m = mask if axis == 1 else mask.T
        pad = np.zeros((m.shape[0], 1), bool)
        p = np.hstack([pad, m, pad])
        dif = np.diff(p.astype(np.int8), axis=1)
        n = 0
        for row in range(p.shape[0]):
            st = np.flatnonzero(dif[row] == 1)
            en = np.flatnonzero(dif[row] == -1)
            if st.size:
                n += int(((en - st) >= least).sum())
        return n
    d["hline"] = longest_runs(ver, 1, 60) / float(h)     # horizontal rules per row
    d["vline"] = longest_runs(hor, 0, 40) / float(w)     # vertical rules per column
    # A LINE OF TEXT sits on a flat baseline: rows whose ink is far above the
    # rows just above and below.
    ink = hor.mean(axis=1)
    d["rowvar"] = float(np.std(ink) / (np.mean(ink) + 1e-6))
    d["bright"] = float(g.mean())
    return d

TRUTH = json.load(open("_probe/screen_truth.json"))
rows = []
for d, fs in sorted(TRUTH.items()):
    for fn, want in sorted(fs.items()):
        n = numbers(cv2.imread(os.path.join("_probe/scratch/set", d, fn)))
        n["want"] = want; n["vid"] = d[:12]; n["f"] = fn
        rows.append(n)
json.dump(rows, open("_probe/measures.json", "w"))
keys = ["ties", "step", "hline", "vline", "rowvar", "bright"]
print("%-8s " % "" + " ".join("%22s" % k for k in keys))
for want in ("screen", "camera"):
    v = [r for r in rows if r["want"] == want]
    print("%-8s " % want + " ".join(
        "%6.3f %6.3f %6.3f " % tuple(np.percentile([r[k] for r in v], [10, 50, 90])) for k in keys))
print("        " + " ".join("%22s" % "p10 / p50 / p90" for k in keys))
