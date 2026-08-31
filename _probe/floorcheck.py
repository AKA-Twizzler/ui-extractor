"""Does the video's own floor change the right answers?

Runs the REAL spot.stretches over the cached thumbnails of four videos, once
with the fixed line and once with the learned one, and counts screen
stretches and chronological moments -- the two numbers that decide how long a
read takes.
"""
import io, os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot

print("%-26s %6s   %10s %10s   %10s %10s" %
      ("video", "floor", "screens 4.0", "moments", "screens own", "moments"))
for f in sorted(glob.glob("_probe/*thumbs*.npz")):
    z = np.load(f)
    th, ts, sc = z["thumb"], z["t"], z["screen"]
    samples = [{"thumb": th[i], "t": int(ts[i]),
                "call": "screen" if sc[i] else "camera", "frac": 0.0}
               for i in range(len(ts))]
    got = []
    for times in (0.0, spot.FLOOR_TIMES):
        spot.FLOOR_TIMES = times
        runs = spot.stretches(samples)
        screens = [r for r in runs if r["call"] == "screen"]
        mom = sum(len(m["times"]) for m in spot.dense_moments(samples))
        got.append((len(screens), mom))
    name = os.path.basename(f).replace("thumbs_", "").replace(".npz", "")
    print("%-26s %6.2f   %10d %10d   %10d %10d" %
          (name[:26], spot._FLOOR[0] or 0, got[0][0], got[0][1], got[1][0], got[1][1]))
