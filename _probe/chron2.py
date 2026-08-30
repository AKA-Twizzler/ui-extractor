import sys
import cv2
import numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import panes
from rapidocr_onnxruntime import RapidOCR

D = r"G:\Images\How Claude Code Actually Works\Images"
PAIRS = [("00-06-50", "00-07-00"), ("00-01-10", "00-01-20"),
         ("00-07-00", "00-07-10")]
eng = RapidOCR()
for a_n, b_n in PAIRS:
    a = cv2.imread(D + "\\" + a_n + ".png")
    b = cv2.imread(D + "\\" + b_n + ".png")
    print("==", a_n, "vs", b_n)
    if a is None or b is None:
        print("   missing frame"); continue
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.int16)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.int16)
    ba = panes.frame_regions(a, engine=eng) or []
    bb = panes.frame_regions(b, engine=eng) or []
    print("   boxes A:", [tuple(int(v) for v in x) for x in ba])
    print("   boxes B:", [tuple(int(v) for v in x) for x in bb])
    for i, (x0, y0, x1, y1) in enumerate(ba):
        cell = np.abs(ga - gb)[y0:y1, x0:x1]
        if cell.size == 0: continue
        n = int((cell > 8).sum())
        print(f"   A-box {i}: over-bound px {n} ({n/cell.size:.4%}) max {int(cell.max())}")
print("PROBE-DONE")
