# read-only: per-column MEDIAN brightness -> background regions (explorer vs note)
import sys, os, statistics
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
from PIL import Image
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
JOBS = [("00-00-00", (700, 2100)), ("00-00-10", (1750, 2140)), ("00-00-30", (1750, 2140)),
        ("00-04-00", (700, 2100)), ("00-04-10", (400, 2100)), ("00-04-40", (400, 2100)),
        ("00-05-00", (400, 2100)), ("00-05-50", (400, 2100))]
for ts, yb in JOBS:
    im = Image.open(os.path.join(D, ts + ".png")).convert("RGB"); W, H = im.size; px = im.load()
    ys = list(range(yb[0], min(yb[1], H), 4))
    med = [statistics.median(sum(px[x, y]) / 3 for y in ys) for x in range(W)]
    # label each column: 0 black/off, 1 note-bg (~29), 2 explorer-bg (~34-40), 3 other
    def lab(v):
        if v < 12: return "K"
        if 26 <= v <= 31: return "N"
        if 33 <= v <= 41: return "E"
        return "?"
    runs, s = [], 0
    for x in range(1, W + 1):
        if x == W or lab(med[x]) != lab(med[s]):
            if x - s >= 8: runs.append((lab(med[s]), s, x - 1, round(statistics.median(med[s:x]), 1)))
            s = x
    print("== %s" % ts, [(l, a, b) for l, a, b, v in runs if b - a >= 20])
