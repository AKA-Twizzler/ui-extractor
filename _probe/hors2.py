import os, sys
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import shapes
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
for ts in ("00-02-50", "00-03-00", "00-03-30", "00-03-50"):
    g, W, H = shapes._grey(os.path.join(D, ts + ".png"))
    h, w = g.shape
    verts, hors = shapes._sides(g, int(shapes.RUN * h), int(shapes.RUN * w))
    verts, hors = shapes._thin(verts), shapes._thin(hors)
    print("==", ts)
    for want in (71, 401):
        near = [hh for hh in hors if abs(hh[0] - want) <= 8 and hh[1] <= 6]
        near.sort(key=lambda hh: -(hh[2] - hh[1]))
        print("   lines near y=%d that START at the screen edge:" % want,
              ["y=%.0f x%.0f..%.0f" % (a, b, c) for a, b, c in near[:4]] or "none")
