"""Frame-level step-edge density, per video: does a dark room separate from a screen?"""
import sys, glob, os
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc

def measures(bgr):
    bgr = sc.to_working_size(bgr)
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
    hor = np.abs(np.diff(g, axis=1))
    ver = np.abs(np.diff(g, axis=0))
    step = float(((hor > 32).mean() + (ver > 32).mean()) / 2)
    frac = sc.screen_fraction(bgr)[0]
    return frac, step, float(g.mean())

print("%-26s %7s   %-28s %-28s" % ("video", "n", "interface frac  p10/p50/p90", "step density   p10/p50/p90"))
for d in sorted(glob.glob("_probe/scratch/set/*/")):
    fs = sorted(glob.glob(os.path.join(d, "*.png")))
    m = np.array([measures(cv2.imread(f)) for f in fs])
    name = os.path.basename(os.path.normpath(d))[:26]
    print("%-26s %7d   %6.2f %6.2f %6.2f        %6.4f %6.4f %6.4f     bright %3.0f"
          % (name, len(fs),
             *np.percentile(m[:, 0], [10, 50, 90]),
             *np.percentile(m[:, 1], [10, 50, 90]), np.median(m[:, 2])))
