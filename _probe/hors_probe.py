import os, sys
import shapes
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
for ts in ("00-02-50", "00-03-00", "00-03-30", "00-03-50"):
    g, W, H = shapes._grey(os.path.join(D, ts + ".png"))
    h, w = g.shape
    least_v, least_h = int(shapes.RUN * h), int(shapes.RUN * w)
    verts, hors = shapes._sides(g, least_v, least_h)
    verts, hors = shapes._thin(verts), shapes._thin(hors)
    print("==", ts, " working space %dx%d  least_h=%d" % (w, h, least_h))
    for want in (85, 415):
        near = [hh for hh in hors if abs(hh[0] - want) <= 6]
        near.sort(key=lambda hh: hh[1])
        print("   horizontals within 6px of y=%d: %d" % (want, len(near)))
        for hh in near[:6]:
            print("        y=%.0f  x %.0f..%.0f  (len %.0f)" % (hh[0], hh[1], hh[2], hh[2] - hh[1]))
