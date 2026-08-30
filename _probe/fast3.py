#!/usr/bin/env python3
"""Measure the tie-based pane gate on the frames whose answers are known.

Per pane of four known moments: the max block-mean of the tie map under the
pane (blocks sized as the calibrated grid cells), and the verdict at the
calibrated bound. Known answers:
  works 00:07:29  pane with the Screenshot table (right side)  -> interface
  works 00:01:52  the Finder window pane -> interface; the room -> camera
  qna   00:02:00  chat column -> interface; camera strips -> camera
  7-24  00:09:04  the Chrome window -> interface
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")

import cv2
import numpy as np

import panes
import screenness

FRAMES = [
    ("works 00:07:29", r"G:\Images\How Claude Code Actually Works\Images\00-07-29.png"),
    ("works 00:01:52", r"G:\Images\How Claude Code Actually Works\Images\00-01-52.png"),
    ("qna 00:02:00", r"G:\Images\Live Q&A Answering Questions About AI Automation\Images\00-02-00.png"),
    ("7-24 00:09:04", r"G:\Images\AI Automation + Sales With Jarvis (7-24-26)\Images\00-09-04.png"),
]


def block_max(ties, box, bh, bw):
    x0, y0, x1, y1 = box
    crop = ties[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return 0.0
    best = 0.0
    for by in range(0, crop.shape[0], bh):
        for bx in range(0, crop.shape[1], bw):
            b = crop[by:by + bh, bx:bx + bw]
            if b.size >= 64:
                best = max(best, float(b.mean()))
    if best == 0.0:
        best = float(crop.mean())
    return best


def main():
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    for name, path in FRAMES:
        old = path.replace(r"\Images" + "\\", "\\", 1) \
            if not os.path.exists(path) else path
        alt = path.replace("\\Images\\00-", "\\00-")
        use = path if os.path.exists(path) else alt
        if not os.path.exists(use):
            print(f"{name}: no frame at {path}")
            continue
        img = cv2.imread(use)
        work = screenness.to_working_size(img)
        ties = screenness.tie_map(work).astype(np.float32)
        rows, cols = screenness.GRID
        bh = max(8, work.shape[0] // rows)
        bw = max(8, work.shape[1] // cols)
        sc = work.shape[1] / img.shape[1]
        print(f"== {name}  ({img.shape[1]}x{img.shape[0]})")
        for pi, box in enumerate(panes.frame_regions(img, engine=engine)):
            wb = tuple(int(v * sc) for v in box)
            m = block_max(ties, wb, bh, bw)
            call = "interface" if m >= screenness.CELL_IS_SCREEN else "camera"
            print(f"   pane {pi}  {box[2]-box[0]:>5}x{box[3]-box[1]:<5} "
                  f"block-max {m:.3f}  -> {call}")
    print("\nfast3 done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
