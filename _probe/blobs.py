import sys, cv2, numpy as np
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, overlay, shapes

def blobs_of(img, box, tall=0.14, wide=0.30):
    x0, y0, x1, y1 = [int(round(v)) for v in box[:4]]
    w, h = x1 - x0, y1 - y0
    strip = img[max(0, y0):y0 + max(24, int(tall * h)),
                max(0, x0):x0 + max(80, int(wide * w))]
    g = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    back = float(np.median(g))
    mask = (np.abs(g.astype(np.int16) - back) > 14).astype(np.uint8)
    n, lab, stats, mids = cv2.connectedComponentsWithStats(mask, 8)
    out = []
    for i in range(1, n):
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        if bw < 4 or bh < 4 or bw > 0.25 * strip.shape[1]:
            continue
        if abs(bw - bh) > 0.45 * max(bw, bh) or area < 0.45 * bw * bh:
            continue
        out.append((mids[i][0], mids[i][1], (bw + bh) / 2.0))
    out.sort()
    return out, strip.shape

for key, stamp in (("works", "00:01:52"), ("memfiles", "00:00:00"),
                   ("post", "00:00:30"), ("obsidian", "00:07:30")):
    img = cv2.imread(checks.frame(key, stamp))
    boxes = [tuple(int(v) for v in r[:4]) for r in overlay.windows(img)]
    boxes += [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)]
    print("===", key, stamp)
    for b in boxes[:3]:
        got, shape = blobs_of(img, b)
        first = got[:4]
        print("   %-26s strip %dx%d  first blobs: %s" % (
            str(b), shape[1], shape[0],
            ["(x %.0f=%.2f, y %.0f=%.2f, r %.0f)" % (
                x, x / shape[1], y, y / shape[0], r) for x, y, r in first]))
