import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, panes, overlay
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
png = sys.argv[1]
img = cv2.imread(png)
print("frame", img.shape[1], "x", img.shape[0])
print("windows found:")
for b in overlay.windows(img):
    print("   ", b)
print("regions:")
for i, b in enumerate(panes.frame_regions(img, engine=eng)):
    print(f"    r{i} {b}  w={b[2]-b[0]} h={b[3]-b[1]}")
res, _ = eng(png)
print("text boxes on the whole frame:")
for box, t, s in (res or []):
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    print(f"    x {min(xs):5.0f}..{max(xs):5.0f}  y {min(ys):5.0f}..{max(ys):5.0f}  {t!r}")
