# diagA: measure the card renders' column edges (read only)
import numpy as np
from PIL import Image
D = "/mnt/g/AI/Ethereal/ui-extractor/_probe/cmp-f12/png/"
def segments(img, y0, y1, x0, x1, tol=3, minlen=4):
    med = np.median(img[y0:y1, x0:x1], axis=0); segs = []; s = 0; n = med.shape[0]
    for x in range(1, n + 1):
        if x == n or np.abs(med[x] - med[s]).max() > tol:
            if x - s >= minlen: segs.append((x0 + s, x0 + x - 1, tuple(int(v) for v in med[s])))
            s = x
    return segs
def ink(img, y0, y1, x0, x1, thr=120, minrows=2):
    band = img[y0:y1, x0:x1]; cnt = (band.max(axis=2) > thr).sum(axis=0)
    cols = np.nonzero(cnt >= minrows)[0]
    if len(cols) == 0: return None
    cum = np.cumsum(cnt); tot = int(cum[-1])
    return dict(first=x0 + int(cols[0]), last=x0 + int(cols[-1]), p1=x0 + int(np.searchsorted(cum, .01 * tot)), p99=x0 + int(np.searchsorted(cum, .99 * tot)))
for card, cols_band, text_band, tab_band in [("card-01", (300, 1150), (150, 1180), (8, 30)), ("card-02", (300, 600), (60, 130), (8, 30)), ("card-03", (300, 1500), (200, 1900), (8, 30))]:
    img = np.asarray(Image.open(D + card + ".png").convert("RGB")).astype(np.int16)
    H, W = img.shape[:2]
    print("=====", card, "size", W, "x", H)
    print("  colour segments y %d-%d:" % cols_band)
    for s in segments(img, cols_band[0], cols_band[1], 0, W): print("     x %4d-%4d rgb%s" % s)
    # the doc column begins after the explorer's border; find text ink right of x=200 (card-01/03) or 44 (card-02)
    left = 200 if card != "card-02" else 44
    print("  text ink y %d-%d x %d-%d ->" % (text_band[0], text_band[1], left, W), ink(img, text_band[0], text_band[1], left, W))
    print("  tab ink  y %d-%d ->" % tab_band, ink(img, tab_band[0], tab_band[1], 160, W))
