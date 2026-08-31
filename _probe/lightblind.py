"""Compare thumbnails in a way a change of room lighting cannot fake.

The webcam room is lit by colour-changing lamps: green, then red, then purple.
Every one of those is a huge grey change over the whole frame while nothing
readable has changed at all. Three ways to compare, per video:

  grey   what the code does now: mean absolute grey difference
  norm   each thumb's own brightness and contrast removed first
  edge   the step edges only -- where the ink is, not how bright the room is
"""
import os, sys, glob
import cv2, numpy as np

def norm(t):
    t = t.astype(np.float32)
    return (t - t.mean()) / (t.std() + 1e-6)

def edges(t):
    g = t.astype(np.int16)
    e = np.zeros(t.shape, np.float32)
    e[:, :-1] = np.abs(np.diff(g, axis=1)) > 20
    return cv2.blur(e, (3, 3))

print("%-24s %-22s %-22s %-22s" % ("video", "grey  p5/p50/p95", "norm  p5/p50/p95", "edge  p5/p50/p95"))
for f in sorted(glob.glob("_probe/*thumbs*.npz")):
    th = np.load(f)["thumb"]
    g = [float(np.abs(a.astype(np.float32) - b.astype(np.float32)).mean())
         for a, b in zip(th, th[1:])]
    n = [float(np.abs(norm(a) - norm(b)).mean()) for a, b in zip(th, th[1:])]
    e = [float(np.abs(edges(a) - edges(b)).mean()) for a, b in zip(th, th[1:])]
    name = os.path.basename(f).replace("thumbs_", "").replace(".npz", "")[:24]
    print("%-24s " % name + " ".join(
        "%6.3f %6.3f %6.3f  " % tuple(np.percentile(v, [5, 50, 95])) for v in (g, n, e)))
