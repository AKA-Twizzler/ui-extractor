# diagA: measure the Obsidian window's edges and the note column off the frames (read only)
import numpy as np
from PIL import Image
D = "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/"
def load(ts):
    return np.asarray(Image.open(D + ts.replace(":", "-") + ".png").convert("RGB")).astype(np.int16)
def segments(img, y0, y1, x0, x1, tol=4, minlen=6):
    med = np.median(img[y0:y1, x0:x1], axis=0)
    segs = []; s = 0; n = med.shape[0]
    for x in range(1, n + 1):
        if x == n or np.abs(med[x] - med[s]).max() > tol:
            if x - s >= minlen: segs.append((x0 + s, x0 + x - 1, tuple(int(v) for v in med[s])))
            s = x
    return segs
def ink(img, y0, y1, x0, x1, thr=110, minrows=2):
    band = img[y0:y1, x0:x1]
    cnt = (band.max(axis=2) > thr).sum(axis=0)
    cols = np.nonzero(cnt >= minrows)[0]
    if len(cols) == 0: return None
    cum = np.cumsum(cnt); tot = int(cum[-1])
    p1 = int(np.searchsorted(cum, 0.01 * tot)); p99 = int(np.searchsorted(cum, 0.99 * tot))
    return dict(first=x0 + int(cols[0]), last=x0 + int(cols[-1]), p1=x0 + p1, p99=x0 + p99, ink=tot)
full = dict(cols=(330, 1100, 0, 800), text=(330, 1140, 600, 3840), crumb=(272, 296, 600, 3800),
            title=(370, 405, 600, 3800), props=(445, 475, 600, 3800), h1=(780, 815, 600, 3800), tab=(215, 245, 400, 1000))
plan = {
    "00:00:00": dict(cols=(250, 460, 0, 800), text=(1180, 2140, 1420, 3840), crumb=(272, 296, 600, 3800),
                     title=(370, 405, 600, 3800), props=(445, 475, 600, 3800), tab=(215, 245, 400, 1000)),
    "00:00:10": dict(title=(40, 130, 0, 3840), text=(1700, 1900, 1800, 3840), props=(215, 260, 1900, 3840)),
    "00:00:30": dict(title=(40, 130, 0, 3840), text=(1700, 1900, 1800, 3840)),
    "00:04:00": dict(cols=(900, 2100, 0, 2000), tab=(250, 285, 1500, 2400)),
    "00:04:10": full, "00:04:40": full, "00:05:00": full, "00:05:10": full,
    "00:05:20": full, "00:05:30": full, "00:05:40": full, "00:05:50": full,
}
for ts, bands in plan.items():
    img = load(ts)
    print("=====", ts, "frame", img.shape[1], "x", img.shape[0])
    for name, (y0, y1, x0, x1) in bands.items():
        if name == "cols":
            print("  column colour segments over y %d-%d:" % (y0, y1))
            for s in segments(img, y0, y1, x0, x1):
                print("     x %4d-%4d  rgb%s" % s)
        else:
            r = ink(img, y0, y1, x0, x1)
            print("  %-6s band y %d-%d x %d-%d -> %s" % (name, y0, y1, x0, x1, r))
