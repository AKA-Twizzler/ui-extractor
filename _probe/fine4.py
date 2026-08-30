"""Two measurements before the camera-word fix is built.

1. A burst change map for the install moment: re-grab the burst, median it,
   and measure per-word change -- the webcam inset should move while screen
   text holds still to within compression noise.

2. The standing-text internals on the works looks: "Har" (the cap) was
   admitted as drawn-on. Print every candidate's glyphs/ground/still/moving
   numbers to see which test let it through.
"""
import sys
import tempfile
import cv2
import numpy as np

sys.path.insert(0, ".")
import capture
import note_reader
import overlay

INSTALL = ("G:/Video/Install Claude Code and-or the AI Memory Vault",
           "00:07:14")
WORDS = ("hat", "fifine", "daily notes", "2026-07-22", "cancel",
         "search app store", "that can open", "orange", "network")

import glob
import os

vid = sorted(glob.glob(INSTALL[0] + "/*.mp4"))[0]

print("=== 1. burst change map, install 00:07:14 ===")
with tempfile.TemporaryDirectory() as work:
    files = capture._ffmpeg_burst(vid, capture._to_seconds(INSTALL[1]),
                                  capture.BURST_SECONDS, work)
    frames = [cv2.imread(f, cv2.IMREAD_COLOR) for f in files]
    frames = [f for f in frames if f is not None]
    print(f"burst of {len(frames)} frames")
    med = capture._median_stack(frames)
    change = np.zeros(med.shape[:2], np.uint8)
    for f in frames:
        d = np.abs(f.astype(np.int16) - med.astype(np.int16)).max(axis=2)
        change = np.maximum(change, d.astype(np.uint8))
    floor = float(np.median(change))
    p90 = float(np.percentile(change, 90))
    print(f"frame change floor (median) {floor:.1f}, p90 {p90:.1f}")

    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    frame_png = ("G:/Images/Install Claude Code and-or the AI Memory Vault/"
                 "00-07-14.png")
    res, _ = eng(frame_png)
    for box, text, _ in (res or []):
        low = " ".join(text.strip().lower().split())
        if not any(n in low for n in WORDS):
            continue
        x0 = int(min(p[0] for p in box)); x1 = int(max(p[0] for p in box))
        y0 = int(min(p[1] for p in box)); y1 = int(max(p[1] for p in box))
        patch = change[y0:y1, x0:x1]
        print(f"  {text.strip()[:36]!r:40} change p50 "
              f"{float(np.median(patch)):6.1f}  p90 "
              f"{float(np.percentile(patch, 90)):6.1f}")

print()
print("=== 2. standing-text internals, works looks ===")
paths = sorted(glob.glob(
    "G:/Images/How Claude Code Actually Works/_looks/look_*.png"))
shots = [cv2.imread(p) for p in paths]
shots = [s for s in shots if s is not None]
print(f"{len(shots)} looks, shapes {sorted({s.shape for s in shots})}")
stack = np.stack([s.astype(np.int16) for s in shots])
change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
still = float(np.percentile(change, 25))
moving = float(np.percentile(change, overlay.STILLEST))
print(f"still(p25) {still:.1f}   moving(p{overlay.STILLEST}) {moving:.1f}")
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
res, _ = eng(paths[0])
for box, text, _conf in (res or []):
    x0 = int(min(q[0] for q in box)); x1 = int(max(q[0] for q in box))
    y0 = int(min(q[1] for q in box)); y1 = int(max(q[1] for q in box))
    if x1 - x0 < 14 or y1 - y0 < 8:
        continue
    gray = cv2.cvtColor(shots[0][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    ink = note_reader.ink_mask(gray)
    if ink.sum() < 25 or (~ink).sum() < 25:
        continue
    here = change[y0:y1, x0:x1]
    glyphs = float(np.median(here[ink]))
    ground = float(np.median(here[~ink]))
    admitted = not (ground <= still or glyphs > ground * overlay.GROUND_SHARE
                    or glyphs > moving)
    mark = "ADMITTED" if admitted else "        "
    print(f"  {mark} {text.strip()[:30]!r:34} glyphs {glyphs:6.1f} "
          f"ground {ground:6.1f}  at {x0},{y0}")
