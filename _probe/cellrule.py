"""Sweep the per-cell rule and the two verdict lines against the 120 frames."""
import os, sys, json, itertools
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

TRUTH = json.load(open("_probe/screen_truth.json"))
CELLS = []

def maps(bgr):
    bgr = sc.to_working_size(bgr)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gi = g.astype(np.int16)
    ties = sc.tie_map(bgr).astype(np.float32)
    st = np.zeros(g.shape, np.float32)
    st[:, :-1] = np.abs(np.diff(gi, axis=1)) > 32
    st[:-1, :] = np.maximum(st[:-1, :], np.abs(np.diff(gi, axis=0)) > 32)
    h, w = g.shape
    r, c = sc.GRID
    T = np.zeros(sc.GRID, np.float32); S = np.zeros(sc.GRID, np.float32)
    B = np.zeros(sc.GRID, np.float32); V = np.zeros(sc.GRID, np.float32)
    for i in range(r):
        y0, y1 = i * h // r, (i + 1) * h // r
        for j in range(c):
            x0, x1 = j * w // c, (j + 1) * w // c
            cell = g[y0:y1, x0:x1]
            T[i, j] = ties[y0:y1, x0:x1].mean()
            S[i, j] = st[y0:y1, x0:x1].mean()
            B[i, j] = cell.mean()
            V[i, j] = cell.std()
    return T, S, B, V

for d, fs in sorted(TRUTH.items()):
    for fn, want in sorted(fs.items()):
        CELLS.append((maps(cv2.imread(os.path.join("_probe/scratch/set", d, fn))), want, d, fn))
print("measured %d frames" % len(CELLS))

out = []
for tie, step, var, cam, scr in itertools.product(
        [0.45, 0.55, 0.65], [0.0, 0.002, 0.005, 0.010],
        [0, 8, 14, 20, 28], [0.02, 0.05, 0.08, 0.12], [0.20, 0.28, 0.35, 0.45]):
    if cam >= scr: continue
    n = {"right": 0, "wrong": 0, "unsure": 0}
    lost = 0
    for (T, S, B, V), want, d, fn in CELLS:
        frac = float(((T >= tie) & (S >= step) & (V >= var)).mean())
        got = "camera" if frac <= cam else "screen" if frac >= scr else "uncertain"
        n["unsure" if got == "uncertain" else "right" if got == want else "wrong"] += 1
        if want == "screen" and got == "camera":
            lost += 1
    out.append((lost, n["wrong"], n["unsure"], tie, step, var, cam, scr, n["right"]))
out.sort()
print("%5s %6s %6s %6s   %5s %6s %4s %5s %5s" %
      ("lost", "wrong", "unsure", "right", "tie", "step", "var", "cam", "scr"))
for lost, w, u, tie, step, var, cam, scr, r in out[:16]:
    print("%5d %6d %6d %6d   %5.2f %6.3f %4d %5.2f %5.2f" % (lost, w, u, r, tie, step, var, cam, scr))
