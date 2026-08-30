"""Advance per ROW, not pooled over all of them."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, statistics
import note_reader, console_reader as cr

for png in sys.argv[1:]:
    bgr = cv2.imread(png)
    if bgr is None:
        print(f"{png}: nothing"); continue
    up = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3),
                    interpolation=cv2.INTER_LANCZOS4)
    big = png.replace(".png", "_3x.png")
    cv2.imwrite(big, up)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    rows = [r for r in note_reader.tess_rows(big, gray) if r["text"].strip()]
    rows.sort(key=lambda r: r["y0"])
    per = []
    for r in rows:
        w = [(x1 - x0) / len(t) for t, x0, x1 in (r.get("words") or [])
             if len(t) >= 3]
        if len(w) >= 2:
            per.append((statistics.median(w), r["text"][:34]))
    pooled = cr.advance_of(rows)
    if not per:
        print(f"\n{os.path.basename(png):38s} too few rows"); continue
    mid = statistics.median([a for a, _ in per])
    spread = statistics.median([abs(a - mid) for a, _ in per]) / mid
    worst = max(abs(a - mid) for a, _ in per) / mid
    print(f"\n{os.path.basename(png)}")
    print(f"  pooled spread {pooled[1]:.3f}   row spread {spread:.3f}   "
          f"worst row {worst:.3f}   rows {len(per)}")
    for a, t in per:
        print(f"     {a:7.2f}  ({a/mid:5.2f}x)  {t!r}")
