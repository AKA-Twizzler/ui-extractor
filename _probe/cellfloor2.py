"""The quiet-cell distribution WHERE THE CODE LOOKS -- inside each stretch."""
import os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot

C = spot.CELL
print("%-24s %6s %7s %7s %7s %7s  %8s %8s %8s" %
      ("video", "floor", "p50", "p90", "p95", "p99", "stretches", "moments", "extra"))
for f in sorted(glob.glob("_probe/*thumbs*.npz")):
    z = np.load(f)
    th, ts, sc = z["thumb"], z["t"], z["screen"]
    samples = [{"thumb": th[i], "t": int(ts[i]),
                "call": "screen" if sc[i] else "camera", "frac": 0.0}
               for i in range(len(ts))]
    runs = spot.stretches(samples)
    q = []
    extra = 0
    for run in runs:
        if run["call"] != "screen":
            continue
        st = [s for s in samples if run["start"] <= s["t"] <= run["end"]]
        if len(st) < 3:
            continue
        thumbs = [np.array(s["thumb"], np.float32) for s in st]
        h, w = thumbs[0].shape
        hc, wc = h // C, w // C
        steps = np.array([np.abs(a - b)[:hc * C, :wc * C]
                          .reshape(hc, C, wc, C).mean(axis=(1, 3))
                          for a, b in zip(thumbs, thumbs[1:])])
        moving = (steps > spot.CELL_BOUND).mean(axis=0) >= spot.CELL_EVERY
        q.append(steps[:, ~moving].ravel())
        for cells in steps:
            big = (cells > spot.CELL_BOUND).mean() >= spot.CELL_BIG
            if big or (cells[~moving] > spot.CELL_BOUND).any():
                extra += 1
    q = np.concatenate(q) if q else np.zeros(1)
    mom = sum(len(m["times"]) for m in spot.dense_moments(samples))
    name = os.path.basename(f).replace("thumbs_", "").replace(".npz", "")[:24]
    print("%-24s %6.2f %7.2f %7.2f %7.2f %7.2f  %8d %8d %8d" %
          (name, spot._FLOOR[0] or 0,
           *[np.percentile(q, p) for p in (50, 90, 95, 99)],
           sum(1 for r in runs if r["call"] == "screen"), mom, extra))
