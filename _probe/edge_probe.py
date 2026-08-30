import os, sys
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import shapes
shapes.WATCH = (0.0, 147.0)
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
for ts in ("00-02-50", "00-03-00", "00-03-30", "00-03-50"):
    print("== %s" % ts, file=sys.stderr)
    shapes._CACHE.clear()
    got = shapes._find_full(os.path.join(D, ts + ".png"))
    hit = [r for r, _g in got if r[0] < 4 and abs(r[2] - 588) < 4]
    print("   -> left-edge rectangle: %s" % bool(hit), file=sys.stderr)
