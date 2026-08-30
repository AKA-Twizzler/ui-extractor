import sys; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2, panes
from rapidocr_onnxruntime import RapidOCR
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
for b in panes.frame_regions(img, engine=RapidOCR()):
    print(b)
