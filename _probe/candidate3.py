import os, sys, json
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc
from candidate import maps, spread

TRUTH = json.load(open("_probe/screen_truth.json"))
INK, CAM, SCR = 0.12, 0.12, 0.35

def call(path):
    T, S = maps(cv2.imread(path))
    frac = float(((T >= sc.CELL_IS_SCREEN) & (spread(S) >= INK)).mean())
    return ("camera" if frac <= CAM else "screen" if frac >= SCR else "uncertain"), frac

print("ink>=%.2f  camera<=%.2f  screen>=%.2f\n" % (INK, CAM, SCR))
print("%-26s %6s %6s %6s   %s" % ("video", "right", "wrong", "unsure", "the ones not settled"))
for d, fs in sorted(TRUTH.items()):
    n = {"right": 0, "wrong": 0, "unsure": 0}
    notes = []
    for fn, want in sorted(fs.items()):
        got, frac = call(os.path.join("_probe/scratch/set", d, fn))
        k = "unsure" if got == "uncertain" else "right" if got == want else "wrong"
        n[k] += 1
        if k != "right":
            notes.append("%s %s->%s %.2f" % (fn[1:7].lstrip("0") or "0", want[:3], got[:3], frac))
    print("%-26s %6d %6d %6d   %s" % (d[:26], n["right"], n["wrong"], n["unsure"],
                                      "  ".join(notes[:6]) + (" ..." if len(notes) > 6 else "")))
