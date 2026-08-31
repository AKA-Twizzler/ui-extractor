"""Keep the tie map for WHERE, and gate the verdict on whether anything was
drawn on the frame at all."""
import json, numpy as np
rows = json.load(open("_probe/measures.json"))
print("%6s   %6s %6s %6s   %s" % ("step<", "right", "wrong", "unsure", "what it costs"))
for s in [0.0, 0.008, 0.012, 0.016, 0.020, 0.024, 0.028, 0.032]:
    n = {"right": 0, "wrong": 0, "unsure": 0}
    for r in rows:
        if r["step"] < s:
            got = "camera"
        else:
            got = ("camera" if r["ties"] <= 0.08 else
                   "screen" if r["ties"] >= 0.35 else "uncertain")
        n["unsure" if got == "uncertain" else "right" if got == r["want"] else "wrong"] += 1
    # which screens were thrown away
    lost = [r for r in rows if r["want"] == "screen" and r["step"] < s]
    print("%6.3f   %6d %6d %6d   %d real screen(s) lost" %
          (s, n["right"], n["wrong"], n["unsure"], len(lost)))
