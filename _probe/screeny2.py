import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np
import screenness, overlay
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for p in sys.argv[1:]:
    img = cv2.imread(p)
    work = screenness.to_working_size(img)
    cells = screenness.cell_scores(work)
    mask = cells >= screenness.CELL_IS_SCREEN
    print(f"\n{os.path.basename(p)}  native {img.shape[1]}x{img.shape[0]}"
          f"  work {work.shape[1]}x{work.shape[0]}  cells>= {mask.mean():.3f}")
    for row in cells:
        print("      " + " ".join(f"{v:.2f}" for v in row))
    for n, r0, r1, c0, c1 in screenness.clusters(mask):
        h, w = work.shape[:2]
        rows, cols = screenness.GRID
        y0, y1 = r0*h//rows, (r1+1)*h//rows
        x0, x1 = c0*w//cols, (c1+1)*w//cols
        crop = work[max(0,y0-8):min(h,y1+8), max(0,x0-8):min(w,x1+8)]
        res, _ = eng(crop) if crop.size else (None, None)
        nb = len(res) if res else 0
        print(f"   cluster cells={n} rows {r0}-{r1} cols {c0}-{c1} "
              f"crop {crop.shape[1]}x{crop.shape[0]} boxes={nb} "
              f"aligned={screenness.rows_aligned(res) if res else False}")
