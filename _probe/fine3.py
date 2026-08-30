"""Per-word tie measurement: does a word's own patch say camera or screen?

Fault 1: words off the webcam inset (the cap's "Hat", the mic's "fifine")
enter the record beside real screen words. Measure, for each interesting word
on the install frame, the exact-tie fraction of the pixels in and around its
box, at native resolution -- painted text sits on a painted ground, camera
text sits on photographed cloth. Also: does any rectangle finder see the
inset itself?
"""
import sys
import cv2
import numpy as np

sys.path.insert(0, ".")
import overlay
import screenness

FRAME = "G:/Images/Install Claude Code and-or the AI Memory Vault/00-07-14.png"
WORDS = ("hat", "fifine", "daily notes", "2026-07-22", "cancel",
         "search app store", "cowboy", "airdrop", "network", "orange")


def tie_frac(bgr):
    if bgr.size == 0 or min(bgr.shape[:2]) < 2:
        return float("nan")
    return float(screenness.tie_map(bgr).mean())


bgr = cv2.imread(FRAME)
h, w = bgr.shape[:2]
print(f"frame {w}x{h}")
print("windows():", overlay.windows(bgr))
print("panels():", [p for p in overlay.panels(bgr)])

from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
res, _ = eng(FRAME)
print(f"\n{len(res or [])} words on the frame; the interesting ones:")
for box, text, conf in (res or []):
    low = " ".join(text.strip().lower().split())
    if not any(n in low for n in WORDS):
        continue
    x0 = int(min(p[0] for p in box)); x1 = int(max(p[0] for p in box))
    y0 = int(min(p[1] for p in box)); y1 = int(max(p[1] for p in box))
    tall = y1 - y0
    grow = tall  # a ring one text-height wide around the word
    X0, Y0 = max(0, x0 - grow), max(0, y0 - grow)
    X1, Y1 = min(w, x1 + grow), min(h, y1 + grow)
    inside = tie_frac(bgr[y0:y1, x0:x1])
    around = tie_frac(bgr[Y0:Y1, X0:X1])
    print(f"  {text.strip()[:36]!r:40} {x0:4},{y0:4}-{x1:4},{y1:4}"
          f"  box {inside:.2f}  with ring {around:.2f}")
