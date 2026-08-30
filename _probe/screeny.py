import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np
import screenness, overlay
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for p in sys.argv[1:]:
    img = cv2.imread(p)
    cells = screenness.cell_scores(img)
    share = (cells > screenness.CELL_IS_SCREEN).mean()
    regs = screenness.ui_regions(img, eng)
    wins = overlay.windows(img)
    print(f"\n{os.path.basename(p)}  {img.shape[1]}x{img.shape[0]}")
    print(f"   cells over {screenness.CELL_IS_SCREEN}: {share:.3f}   "
          f"(sure camera under {screenness.SURE_CAMERA}, "
          f"sure screen over {screenness.SURE_SCREEN})")
    print(f"   ui_regions: {len(regs)}   windows found: {len(wins)} {wins[:3]}")
    print("   cell grid:")
    for row in cells:
        print("      " + " ".join(f"{v:.2f}" for v in row))
