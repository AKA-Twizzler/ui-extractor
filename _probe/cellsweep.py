"""If the cell bound came from the video's own cell noise, what happens?

Cell floor = the median step of every cell across the whole video, which is a
robust read on "nothing happening" because most cells are quiet in most steps.
Bound = max(2.0, floor * k). Prints moments per video for each k.
"""
import os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot

C = spot.CELL
KS = [0, 2, 3, 4, 6, 8]

def moments(samples, bound):
    n = 0
    for run in spot.stretches(samples):
        if run["call"] != "screen":
            continue
        st = [s for s in samples if run["start"] <= s["t"] <= run["end"]]
        n += 1
        if len(st) < 3:
            continue
        thumbs = [np.array(s["thumb"], np.float32) for s in st]
        h, w = thumbs[0].shape
        hc, wc = h // C, w // C
        steps = np.array([np.abs(a - b)[:hc * C, :wc * C]
                          .reshape(hc, C, wc, C).mean(axis=(1, 3))
                          for a, b in zip(thumbs, thumbs[1:])])
        moving = (steps > bound).mean(axis=0) >= spot.CELL_EVERY
        for cells in steps:
            big = (cells > bound).mean() >= spot.CELL_BIG
            if big or (cells[~moving] > bound).any():
                n += 1
    return n

print("%-24s %7s " % ("video", "cellfl") + " ".join("%8s" % ("k=%g" % k) for k in KS))
for f in sorted(glob.glob("_probe/*thumbs*.npz")):
    z = np.load(f)
    th, ts, sc = z["thumb"], z["t"], z["screen"]
    samples = [{"thumb": th[i], "t": int(ts[i]),
                "call": "screen" if sc[i] else "camera", "frac": 0.0}
               for i in range(len(ts))]
    t = th.astype(np.float32)
    h, w = t.shape[1], t.shape[2]
    hc, wc = h // C, w // C
    allsteps = np.array([np.abs(a - b)[:hc * C, :wc * C]
                         .reshape(hc, C, wc, C).mean(axis=(1, 3))
                         for a, b in zip(t, t[1:])])
    fl = float(np.median(allsteps))
    name = os.path.basename(f).replace("thumbs_", "").replace(".npz", "")[:24]
    got = [moments(samples, max(spot.CELL_BOUND, fl * k)) for k in KS]
    print("%-24s %7.2f " % (name, fl) + " ".join("%8d" % g for g in got))
