import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, overlay, note_reader, screenness
from rapidocr_onnxruntime import RapidOCR

video = sys.argv[1]; at = float(sys.argv[2])
paths = overlay.frames_across(video, at, workdir=os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_stand"))
shots = [cv2.imread(p) for p in paths]
shots = [s for s in shots if s is not None]
print(f"{len(shots)} looks, {shots[0].shape[1]}x{shots[0].shape[0]}")
stack = np.stack([s.astype(np.int16) for s in shots])
change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
pct = {p: float(np.percentile(change, p)) for p in (10, 20, 25, 30, 40, 50, 60, 75)}
print("frame change percentiles: " + "  ".join(f"p{k}={v:.0f}" for k, v in pct.items()))

eng = RapidOCR()
regions = screenness.ui_regions(shots[0], eng)
back = shots[0].shape[1] / screenness.WORK_WIDTH
boxes = [tuple(int(v * back) for v in r["box"]) for r in regions]
print(f"{len(regions)} confirmed interface regions: {boxes}")

res, _ = eng(paths[0])
rows = []
for box, text, _c in (res or []):
    x0 = int(min(q[0] for q in box)); x1 = int(max(q[0] for q in box))
    y0 = int(min(q[1] for q in box)); y1 = int(max(q[1] for q in box))
    if x1 - x0 < 14 or y1 - y0 < 8:
        continue
    gray = cv2.cvtColor(shots[0][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    ink = note_reader.ink_mask(gray)
    if ink.sum() < 25 or (~ink).sum() < 25:
        continue
    here = change[y0:y1, x0:x1]
    g = float(np.median(here[ink])); gr = float(np.median(here[~ink]))
    cx, cy = (x0+x1)//2, (y0+y1)//2
    inside = any(a <= cx < c and b <= cy < d for a, b, c, d in boxes)
    passes = not (gr <= pct[25] or g > gr or g > pct[40])
    rows.append((passes, inside, g, gr, text[:34]))
for passes, inside, g, gr, t in sorted(rows, reverse=True)[:40]:
    print(f"  {'ADMITTED' if passes else '   -    '} "
          f"{'in-UI ' if inside else 'on-wall'} glyphs={g:6.1f} ground={gr:6.1f}  {t}")
