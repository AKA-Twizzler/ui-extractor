"""Does the MEASURED zoom agree with something it never looked at?

zoom.py measures how far a frame is zoomed in by shrinking it until it fits
inside an unzoomed frame of the same screen. Nothing in that says anything
about text. So here is a check by a different method entirely: a Finder list's
ROW PITCH, counted from the ink by the pixels-first reader, is a fixed number
of SCREEN pixels; seen through a zoom it grows by exactly 1/scale. So

    row pitch in the frame  x  measured scale  =  the same number every time

if the measurement is right, and scatter if it is not.
"""
import sys, os, json, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import zoom

IMG = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
CACHE = next((d for d in (os.path.join(HERE, "pixfirst-cache.warm"),
                          os.path.join(HERE, "pixfirst-cache"))
              if os.path.isdir(d)), os.path.join(HERE, "pixfirst-cache"))

recs = {}
for f in sorted(glob.glob(os.path.join(CACHE, "*.json"))):
    r = json.load(open(f, encoding="utf-8"))
    if r.get("pitch"):
        recs.setdefault(r["frame"], []).append(r)

# the reference: the first frame that plainly shows the whole menu bar
ref = None
for name in sorted(recs):
    if zoom.unzoomed_by_bar(os.path.join(IMG, name)) is not None:
        ref = os.path.join(IMG, name); break
print("reference frame:", os.path.basename(ref or "NONE"))

print("%-12s %6s %6s %8s   %s" % ("frame", "scale", "score", "pitch", "pitch x scale"))
prod = []
for name in sorted(recs):
    got = zoom.measure(os.path.join(IMG, name), ref)
    if got is None:
        print("%-12s   no measurement" % name); continue
    s, x0, y0, sc = got
    for r in recs[name]:
        # the pitch in the record is already in the FRAME's own pixels
        pitch = float(r["pitch"])
        prod.append(pitch * s)
        print("%-12s %6.2f %6.2f %8.1f   %8.1f" % (name, s, sc, pitch, pitch * s))
if prod:
    prod.sort()
    med = prod[len(prod) // 2]
    off = [abs(p - med) / med for p in prod]
    print("\nmedian %.1f   worst %.0f%% off   within 10%%: %d of %d"
          % (med, 100 * max(off), sum(1 for o in off if o <= 0.10), len(prod)))
