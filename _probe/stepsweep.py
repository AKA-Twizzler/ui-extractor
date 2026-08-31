"""A cell is interface when it TIES a lot and has STEP EDGES. Sweep the step line.

Ties alone call a dark room interface: H.264 paints near-black in flat blocks
of one exact value, so neighbours tie everywhere. What a dark room does NOT
have is a step edge -- a neighbour differing by tens of grey levels. Text and
window borders are made of them.
"""
import sys, glob, os
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

STEPS = [0.0, 0.005, 0.01, 0.02, 0.03, 0.05]

def cells(bgr):
    bgr = sc.to_working_size(bgr)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
    ties = sc.tie_map(bgr).astype(np.float32)
    step = np.zeros(g.shape, np.float32)
    step[:, :-1] = np.abs(np.diff(g, axis=1)) > 32
    h, w = g.shape
    r, c = sc.GRID
    T = np.zeros(sc.GRID, np.float32); S = np.zeros(sc.GRID, np.float32)
    for i in range(r):
        y0, y1 = i * h // r, (i + 1) * h // r
        for j in range(c):
            x0, x1 = j * w // c, (j + 1) * w // c
            T[i, j] = ties[y0:y1, x0:x1].mean()
            S[i, j] = step[y0:y1, x0:x1].mean()
    return T, S

print("%-26s %5s " % ("video", "n") + " ".join("%16s" % ("step>=%.3f" % s) for s in STEPS))
print("%-26s %5s " % ("", "") + " ".join("%16s" % "screen/uncert/cam" for s in STEPS))
for d in sorted(glob.glob("_probe/scratch/set/*/")):
    fs = sorted(glob.glob(d + "*.png"))
    tally = []
    for st in STEPS:
        n = {"screen": 0, "uncertain": 0, "camera": 0}
        for f in fs:
            T, S = cells(cv2.imread(f))
            frac = float(((T >= sc.CELL_IS_SCREEN) & (S >= st)).mean())
            v = ("camera" if frac <= sc.SURE_CAMERA else
                 "screen" if frac >= sc.SURE_SCREEN else "uncertain")
            n[v] += 1
        tally.append(n)
    print("%-26s %5d " % (os.path.basename(d.rstrip("/"))[:26], len(fs)) +
          " ".join("%16s" % ("%d/%d/%d" % (t["screen"], t["uncertain"], t["camera"]))
                   for t in tally))
