"""What does a QUIET cell look like, per video?

spot.dense_moments calls a cell an event when it steps past 2.0 grey. That
number was measured on screen recordings. This prints, per video, the whole
distribution of cell steps among the cells that are NOT persistently moving --
the ones the bound is supposed to be judging.
"""
import os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot

C = spot.CELL
print("%-24s %7s %7s %7s %7s %7s %7s  %6s" %
      ("video", "p50", "p75", "p90", "p95", "p99", "max", "past2%"))
for f in sorted(glob.glob("_probe/*thumbs*.npz")):
    z = np.load(f)
    th = z["thumb"].astype(np.float32)
    h, w = th.shape[1], th.shape[2]
    hc, wc = h // C, w // C
    steps = np.array([np.abs(a - b)[:hc * C, :wc * C]
                      .reshape(hc, C, wc, C).mean(axis=(1, 3))
                      for a, b in zip(th, th[1:])])
    moving = (steps > spot.CELL_BOUND).mean(axis=0) >= spot.CELL_EVERY
    q = steps[:, ~moving].ravel()
    name = os.path.basename(f).replace("thumbs_", "").replace(".npz", "")[:24]
    print("%-24s %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f  %5.1f%%  (%d of %d cells quiet)" %
          (name, *[np.percentile(q, p) for p in (50, 75, 90, 95, 99)], q.max(),
           100.0 * (q > spot.CELL_BOUND).mean(), (~moving).sum(), moving.size))
