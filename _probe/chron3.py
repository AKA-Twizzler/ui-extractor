import sys
import cv2
import numpy as np
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import panes
from rapidocr_onnxruntime import RapidOCR

D = r"G:\Images\How Claude Code Actually Works\Images"
STACKED = ["00-00-20","00-00-30","00-00-50","00-01-10","00-01-20","00-01-30",
           "00-01-40","00-01-50","00-02-10","00-02-20","00-03-00","00-04-30",
           "00-04-40","00-05-30","00-05-40","00-06-40","00-06-50","00-07-00",
           "00-07-10","00-07-40","00-08-20"]
eng = RapidOCR()
boxes_of = {}
def boxes(name, img):
    if name not in boxes_of:
        boxes_of[name] = [tuple(int(v) for v in b)
                          for b in (panes.frame_regions(img, engine=eng) or [])]
    return boxes_of[name]

for a_n, b_n in zip(STACKED, STACKED[1:]):
    a = cv2.imread(D + "\\" + a_n + ".png"); b = cv2.imread(D + "\\" + b_n + ".png")
    if a is None or b is None or a.shape != b.shape: continue
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.int16)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.int16)
    d = np.abs(ga - gb)
    for i, (x0, y0, x1, y1) in enumerate(boxes(a_n, a)):
        match = [pb for pb in boxes(b_n, b)
                 if all(abs(x - y) <= 4 for x, y in zip((x0,y0,x1,y1), pb))]
        if not match: continue
        cell = d[y0:y1, x0:x1]
        n8 = int((cell > 8).sum()); n16 = int((cell > 16).sum())
        print(f"{a_n}->{b_n} box{i} ({x1-x0}x{y1-y0}): >8:{n8} >16:{n16} max:{int(cell.max())}")
print("PROBE-DONE")
