"""What the line engine read against what the lattice laid out, line by line."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np
import console_reader as cr
import note_reader

png = sys.argv[1]
bgr = cv2.imread(png)
up = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3),
                interpolation=cv2.INTER_LANCZOS4)
big = png.replace(".png", "_3x.png")
cv2.imwrite(big, up)
gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
mask = note_reader.ink_mask(gray)
rows = [r for r in note_reader.tess_rows(big, gray) if r["text"].strip()]
rows.sort(key=lambda r: r["y0"])
res = cr.read_console(png)
print(f"is_console={res.get('is_console')} why={res.get('why')}")
if not res.get("is_console"):
    raise SystemExit
laid = [l["text"] for l in res["lines"]]
for i, r in enumerate(rows):
    mine = laid[i] if i < len(laid) else ""
    print(f"\n  line engine : {r['text']!r}")
    print(f"  lattice     : {mine!r}")
