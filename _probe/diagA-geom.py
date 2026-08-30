# read-only: measure Obsidian column geometry off the frames
import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
from PIL import Image
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
# (ts, y-band for the column scan, y-band for the body-text ink scan, x-range for ink)
JOBS = [("00-00-00", (900, 1900), (1180, 2140), (600, 3840)),
        ("00-00-10", (1750, 2100), (1700, 2140), (900, 3840)),
        ("00-00-30", (1750, 2100), (1700, 2140), (900, 3840)),
        ("00-04-00", (900, 2100), (300, 2100), (1560, 3840)),
        ("00-04-10", (400, 2100), (400, 2100), (600, 3840)),
        ("00-04-40", (400, 2100), (400, 2100), (600, 3840)),
        ("00-05-00", (400, 2100), (400, 2100), (600, 3840)),
        ("00-05-50", (400, 2100), (400, 2100), (600, 3840))]
for ts, yb, tb, xr in JOBS:
    im = Image.open(os.path.join(D, ts + ".png")).convert("RGB")
    W, H = im.size
    px = im.load()
    ys = range(yb[0], min(yb[1], H), 6)
    col = []
    for x in range(0, W, 1):
        v = [px[x, y] for y in ys]
        col.append(sum(sum(c) / 3 for c in v) / len(v))
    # runs of near-constant brightness
    runs, s = [], 0
    for x in range(1, W):
        if abs(col[x] - col[s]) > 1.5:
            if x - s >= 12:
                runs.append((s, x - 1, round(sum(col[s:x]) / (x - s), 1)))
            s = x
    if W - s >= 12:
        runs.append((s, W - 1, round(sum(col[s:W]) / (W - s), 1)))
    print("== %s  frame %dx%d" % (ts, W, H))
    print("   flat bands:", [(a, b, v) for a, b, v in runs if b - a >= 25][:12])
    # body text ink extent
    ink = [0] * W
    for y in range(tb[0], min(tb[1], H), 3):
        for x in range(xr[0], min(xr[1], W), 2):
            r, g, b = px[x, y]
            if (r + g + b) / 3 > 110:
                ink[x] += 1
    tot = sum(ink)
    if tot:
        run = 0; first = last = None; cum = 0; p1 = p99 = None
        for x in range(W):
            if ink[x]:
                if first is None: first = x
                last = x
            cum += ink[x]
            if p1 is None and cum >= 0.01 * tot: p1 = x
            if p99 is None and cum >= 0.99 * tot: p99 = x
        print("   body-text ink x: first=%s last=%s p1=%s p99=%s" % (first, last, p1, p99))
