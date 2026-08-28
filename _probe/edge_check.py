import os, sys
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import shapes
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
for ts in ("00-02-50", "00-03-00", "00-03-30", "00-03-50", "00-00-00", "00-00-50"):
    shapes._CACHE.clear()
    P = os.path.join(D, ts + ".png")
    W, H = shapes._frame_size(P)
    ws = shapes.windows(P)
    big = [r for r in ws if (r[2]-r[0])*(r[3]-r[1]) >= 0.09*W*H]
    left = [r for r in big if r[0] < 0.02*W]
    print("%s  windows=%d  window-sized=%d  left-edge=%s" % (ts, len(ws), len(big), bool(left)))
    for r in big:
        print("      x %.3f-%.3f y %.3f-%.3f" % (r[0]/W, r[2]/W, r[1]/H, r[3]/H))
