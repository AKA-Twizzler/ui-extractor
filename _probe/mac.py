import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, screenness
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for p in sys.argv[1:]:
    bgr = cv2.imread(p)
    work = screenness.to_working_size(bgr)
    cells = screenness.cell_scores(work)
    frac, _ = screenness.screen_fraction(work)
    regions = screenness.ui_regions(bgr, eng)
    print(f"=== {os.path.basename(os.path.dirname(p))}/{os.path.basename(p)}"
          f"   {bgr.shape[1]}x{bgr.shape[0]}")
    print(f"    tie-fraction of cells >= {screenness.CELL_IS_SCREEN}: {frac*100:.0f}%"
          f"   regions confirmed: {len(regions)}")
    print("    cell scores:")
    for row in cells:
        print("      " + " ".join(f"{v:.2f}" for v in row))
    print(screenness.picture(cells))
