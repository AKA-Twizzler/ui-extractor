import os, sys, itertools
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc
from screenbench import score
from candidate import maps, spread

CACHE = {}
def cells(path):
    if path not in CACHE:
        CACHE[path] = maps(cv2.imread(path))
    return CACHE[path]

def make(low, cam, scr):
    def call_path(path):
        T, S = cells(path)
        frac = float(((T >= sc.CELL_IS_SCREEN) & (spread(S) >= low)).mean())
        return ("camera" if frac <= cam else "screen" if frac >= scr else "uncertain")
    return call_path

import json
TRUTH = json.load(open("_probe/screen_truth.json"))
best = []
for low, cam, scr in itertools.product([0.09, 0.12, 0.16, 0.20, 0.25, 0.30],
                                       [0.02, 0.05, 0.08, 0.12],
                                       [0.15, 0.20, 0.25, 0.28, 0.35]):
    if cam >= scr: continue
    f = make(low, cam, scr)
    n = {"right": 0, "wrong": 0, "unsure": 0}
    for d, fs in TRUTH.items():
        for fn, want in fs.items():
            got = f(os.path.join("_probe/scratch/set", d, fn))
            n["unsure" if got == "uncertain" else "right" if got == want else "wrong"] += 1
    best.append((n["wrong"], n["unsure"], low, cam, scr, n["right"]))
best.sort()
print("%6s %6s %6s   %5s %5s %5s" % ("wrong", "unsure", "right", "ink", "cam", "scr"))
for w, u, low, cam, scr, r in best[:14]:
    print("%6d %6d %6d   %5.2f %5.2f %5.2f" % (w, u, r, low, cam, scr))
