"""Where to set the bar: how many text items make a frame worth reading."""
import json, numpy as np
rows = json.load(open("_probe/confirmed.json"))
for want in ("screen", "camera"):
    v = sorted(r["boxes"] for r in rows if r["want"] == want)
    print("%-8s n=%3d  %s" % (want, len(v), " ".join(str(x) for x in v)))
print()
print("%6s   %6s %6s %6s %6s" % ("boxes>=", "right", "wrong", "lost", "kept in error"))
for bar in [0, 5, 8, 10, 12, 15, 18, 20, 24, 30, 40]:
    lost = sum(1 for r in rows if r["want"] == "screen" and r["boxes"] < bar)
    kept = sum(1 for r in rows if r["want"] == "camera" and r["boxes"] >= bar)
    right = len(rows) - lost - kept
    print("%6d   %6d %6d %6d %6d" % (bar, right, lost + kept, lost, kept))
