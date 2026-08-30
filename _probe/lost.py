import sys, os, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, note_reader as N

png = sys.argv[1]
bgr = cv2.imread(png)
bgr = cv2.resize(bgr, (bgr.shape[1]*3, bgr.shape[0]*3), interpolation=cv2.INTER_LANCZOS4)
big = png.replace(".png", "_3x.png"); cv2.imwrite(big, bgr)
gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY); mask = N.ink_mask(gray)
rows = N.tess_rows(big, gray); rows.sort(key=lambda r: (r["y0"], r["x0"]))
for r in rows:
    r["xh"] = N.row_x_height(mask, r)
body = statistics.median([r["xh"] for r in rows if r["xh"] > 0])
kept = N.note_body(rows, body)
out = {r["y0"]: r for r in kept}
print("note_body verdict, row by row:")
for r in rows:
    k = out.get(r["y0"])
    if k is None:
        print(f"  DROPPED  x0={r['x0']:5d}  {r['text'][:70]}")
    elif k["text"] != r["text"]:
        print(f"  TRIMMED  x0={r['x0']:5d}->{k['x0']:5d}  {k['text'][:70]}")
