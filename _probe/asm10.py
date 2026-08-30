"""Between two captures of the SAME screen, how still are a pane's pixels
-- and how loud is a real change?  Sets the reuse rule for reading only
what changed between moments."""
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import panes
from rapidocr_onnxruntime import RapidOCR

PAIRS = [
    (r"G:\Images\How Claude Code Actually Works\00-07-29.png",
     r"G:\Images\How Claude Code Actually Works\00-07-30.png",
     "same screen, 1s apart"),
    (r"G:\Images\How To Set Up Claude Code With Obsidian\00-02-03.png",
     r"G:\Images\How To Set Up Claude Code With Obsidian\00-02-09.png",
     "same desktop, 6s apart"),
    (r"G:\Images\How Claude Code Actually Works\00-01-52.png",
     r"G:\Images\How Claude Code Actually Works\00-07-29.png",
     "different screens entirely"),
]
eng = RapidOCR()
for a_path, b_path, what in PAIRS:
    a, b = cv2.imread(a_path), cv2.imread(b_path)
    print("==", what)
    if a is None or b is None or a.shape != b.shape:
        print("   shapes differ or a frame is missing:",
              None if a is None else a.shape, None if b is None else b.shape)
        continue
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.int16)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.int16)
    d = np.abs(ga - gb)
    boxes = panes.frame_regions(a, engine=eng) or []
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        cell = d[y0:y1, x0:x1]
        if cell.size == 0:
            continue
        share = float((cell > 8).mean())
        print(f"   pane {i} ({x0},{y0},{x1},{y1}): changed {share:.4%}  "
              f"p99 {int(np.percentile(cell, 99))}  max {int(cell.max())}")
print("PROBE-DONE")
