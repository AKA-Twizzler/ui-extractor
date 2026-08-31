import sys, os, time, glob
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
fr = sorted(glob.glob(os.path.join(D, "*.png")))
fr = [f for f in fr if "-overlay" not in f][:14]
bad = 0
for f in fr:
    t = time.perf_counter()
    try:
        rec = pixfirst.read_frame(f, None, "memory")
        n = len(rec.get("rows") or [])
        print("  ok  %-14s %5.1f s  %2d rows" % (os.path.basename(f)[:14], time.perf_counter()-t, n))
    except Exception as e:
        bad += 1; print("  FAIL %-14s %s: %s" % (os.path.basename(f)[:14], type(e).__name__, e))
print("frames %d, failures %d" % (len(fr), bad))
