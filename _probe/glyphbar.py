"""Does box shape separate a glyph animation from a terminal?"""
import json, numpy as np
rows = json.load(open("_probe/glyphwidth.json"))
RAIN = "Live_Replay___July_6__20"
def show(name, v, key):
    x = sorted(r[key] for r in v if r["n"] >= 5)
    if not x: return print("%-34s none" % name)
    print("%-34s n=%3d   p10 %6.3f  p50 %6.3f  p90 %6.3f" %
          (name, len(x), *np.percentile(x, [10, 50, 90])))
for key, what in (("w", "box width, share of the crop"), ("c", "characters per box")):
    print("\n== %s" % what)
    show("a real screen", [r for r in rows if r["want"] == "screen"], key)
    show("a camera, any video", [r for r in rows if r["want"] == "camera"], key)
    show("  of those, the glyph rain", [r for r in rows if r["want"] == "camera" and r["vid"] == RAIN], key)
    show("  of those, everything else", [r for r in rows if r["want"] == "camera" and r["vid"] != RAIN], key)
