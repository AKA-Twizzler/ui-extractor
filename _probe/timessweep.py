"""How many moments at each multiple of the video's own floor."""
import os, sys, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import spot

KS = [0, 2.5, 4, 6, 8, 12]
print("%-24s %6s " % ("video", "floor") + " ".join("%14s" % ("x%g" % k) for k in KS))
print("%-24s %6s " % ("", "") + " ".join("%14s" % "line str/mom" for k in KS))
for f in sorted(glob.glob("_probe/*thumbs*.npz")):
    z = np.load(f)
    th, ts, sc = z["thumb"], z["t"], z["screen"]
    samples = [{"thumb": th[i], "t": int(ts[i]),
                "call": "screen" if sc[i] else "camera", "frac": 0.0}
               for i in range(len(ts))]
    out = []
    for k in KS:
        spot.FLOOR_TIMES = k
        runs = spot.stretches(samples)
        st = sum(1 for r in runs if r["call"] == "screen")
        mom = sum(len(m["times"]) for m in spot.dense_moments(samples))
        out.append("%4.1f %4d/%4d" % (spot.same_screen_line(), st, mom))
    print("%-24s %6.2f " % (os.path.basename(f).replace("thumbs_", "").replace(".npz", "")[:24],
                            spot._FLOOR[0] or 0) + " ".join("%14s" % o for o in out))
