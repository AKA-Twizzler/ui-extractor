import sys, os, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, note_reader as N

# letters drawn between baseline and x-height: no ascender, no descender
XBAND = set("acemnorsuvwxz")

png = sys.argv[1]
bgr = cv2.imread(png)
bgr = cv2.resize(bgr, (bgr.shape[1]*3, bgr.shape[0]*3), interpolation=cv2.INTER_LANCZOS4)
big = png.replace(".png", "_3x.png")
cv2.imwrite(big, bgr)
gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
mask = N.ink_mask(gray)
rows = N.tess_rows(big, gray)
rows.sort(key=lambda r: (r["y0"], r["x0"]))

def xband_height(row):
    words = row.get("words") or []
    sizes = [N.x_height(mask, row["y0"], row["y1"], w[1], w[2])
             for w in words if any(c in XBAND for c in w[0])]
    sizes = [s for s in sizes if s > 0]
    return float(statistics.median(sizes)) if sizes else 0.0

now, new = [], []
for r in rows:
    r["xh"] = N.row_x_height(mask, r)
    r["xb"] = xband_height(r)
    now.append(r["xh"]); new.append(r["xb"])
bn = statistics.median([v for v in now if v > 0])
bb = statistics.median([v for v in new if v > 0])
print(f"body by current measure {bn:.1f}   by x-band words {bb:.1f}\n")
for r in rows:
    a = r["xh"]/bn if bn else 0
    b = r["xb"]/bb if bb and r["xb"] else 0
    flag = "  <<< " if (a >= 1.10) != (b >= 1.10) else "      "
    print(f"{a:5.2f} {b:5.2f}{flag}{r['text'][:74]}")
