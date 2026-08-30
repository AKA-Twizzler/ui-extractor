import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, panes
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
png = sys.argv[1]
img = cv2.imread(png)
boxes = panes.frame_regions(img, engine=eng)
print(f"{os.path.basename(png)}  frame {img.shape[1]}x{img.shape[0]}  "
      f"{len(boxes)} regions")
for i, box in enumerate(boxes):
    out = png.replace(".png", f"_s{i}.png")
    w = panes.write_box(img, box, out)
    if w is None:
        print(f"  pane {i}: write_box refused it -- SILENT TODAY   box={box}")
        continue
    res, _ = eng(out)
    n = len(res or [])
    print(f"  pane {i}: {n} readings" + ("   <-- SILENT TODAY" if n == 0 else ""))
