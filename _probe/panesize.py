import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, panes, machine
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for png in sys.argv[1:]:
    img = cv2.imread(png)
    print(f"{os.path.basename(os.path.dirname(png))}/{os.path.basename(png)}"
          f"  frame {img.shape[1]}x{img.shape[0]}")
    for i, box in enumerate(panes.frame_regions(img, engine=eng)):
        p = png.replace(".png", f"_z{i}.png")
        if panes.write_box(img, box, p) is None:
            continue
        h, w = cv2.imread(p).shape[:2]
        mpx3 = w * h * 9 / 1e6
        afford = int((machine.READ_PIXELS / float(w * h)) ** 0.5)
        print(f"    pane {i}: {w}x{h}  at 3x = {mpx3:6.1f} Mpx   "
              f"budget allows {min(3, max(1, afford))}x")
