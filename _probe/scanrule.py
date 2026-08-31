"""Score the rule the SKIM actually uses: any cluster of tied cells and the
sample is a screen. Then the same rule with a spread gate on each cell."""
import os, sys, json, itertools
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

TRUTH = json.load(open("_probe/screen_truth.json"))
FRAMES = []
for d, fs in sorted(TRUTH.items()):
    for fn, want in sorted(fs.items()):
        bgr = sc.to_working_size(cv2.imread(os.path.join("_probe/scratch/set", d, fn)))
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        ties = sc.tie_map(bgr).astype(np.float32)
        h, w = g.shape
        r, c = sc.GRID
        T = np.zeros(sc.GRID, np.float32); V = np.zeros(sc.GRID, np.float32)
        for i in range(r):
            y0, y1 = i * h // r, (i + 1) * h // r
            for j in range(c):
                x0, x1 = j * w // c, (j + 1) * w // c
                T[i, j] = ties[y0:y1, x0:x1].mean()
                V[i, j] = g[y0:y1, x0:x1].std()
        FRAMES.append((T, V, want, d))

def run(var, min_cells):
    n = {"right": 0, "wrong": 0}
    lost = 0
    per = {}
    for T, V, want, d in FRAMES:
        mask = (T >= sc.CELL_IS_SCREEN) & (V >= var)
        cands = [x for x in sc.clusters(mask) if x[0] >= min_cells]
        got = "screen" if cands else "camera"
        k = "right" if got == want else "wrong"
        n[k] += 1
        if want == "screen" and got == "camera":
            lost += 1
        p = per.setdefault(d, [0, 0])
        p[0 if k == "right" else 1] += 1
    return n, lost, per

print("%5s %5s   %6s %6s %6s" % ("var", "cells", "right", "wrong", "screens lost"))
for var, mc in itertools.product([0, 6, 10, 14, 18, 22, 26], [2, 3, 4]):
    n, lost, per = run(var, mc)
    print("%5d %5d   %6d %6d %6d" % (var, mc, n["right"], n["wrong"], lost))
print()
for var, mc in ((0, 2), (14, 2), (18, 3)):
    n, lost, per = run(var, mc)
    print("var>=%d cells>=%d:" % (var, mc),
          "  ".join("%s %d/%d" % (d[:12], v[0], v[1]) for d, v in sorted(per.items())))
