"""Assembly probe: do pane boxes sit cleanly inside drawn windows, and do
title strips read?  Measurement before design for the assembled record."""
import os
import sys

import cv2

sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import overlay
import panes
import verify_names
from rapidocr_onnxruntime import RapidOCR

SPECIMENS = [
    r"G:\Images\How Claude Code Actually Works\00-01-52.png",
    r"G:\Images\How Claude Code Actually Works\00-05-36.png",
    r"G:\Images\How Claude Code Actually Works\00-07-29.png",
    r"G:\Images\How To Set Up Claude Code With Obsidian\00-02-09.png",
    r"G:\Images\Jarvis Visualizer with Claude Code\00-01-35.png",
]

eng = RapidOCR()
for path in SPECIMENS:
    img = cv2.imread(path)
    print("==", path, None if img is None else img.shape)
    if img is None:
        continue
    H, W = img.shape[:2]
    wins = overlay.windows(img) or []
    print("windows:", wins)
    boxes = panes.frame_regions(img, engine=eng) or []
    for i, b in enumerate(boxes):
        x0, y0, x1, y1 = b
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        inside = [wi for wi, (a, t, c, d) in enumerate(wins)
                  if a <= cx < c and t <= cy < d]
        shares = []
        for (a, t, c, d) in wins:
            ox = max(0, min(x1, c) - max(x0, a))
            oy = max(0, min(y1, d) - max(y0, t))
            shares.append(round(ox * oy / max(1, (x1 - x0) * (y1 - y0)), 2))
        print(f"pane {i}: box={tuple(int(v) for v in b)} "
              f"center-in={inside} area-shares={shares}")
    for wi, (a, t, c, d) in enumerate(wins):
        wh = d - t
        for frac in (0.04, 0.06, 0.09):
            sh = max(24, int(wh * frac))
            strip = img[t:t + sh, a:c]
            if strip.size == 0:
                continue
            big = cv2.resize(strip, None, fx=3, fy=3,
                             interpolation=cv2.INTER_CUBIC)
            tag = os.path.basename(path)[:8].replace(":", "-")
            tmp = rf"G:\AI\Ethereal\ui-extractor\_probe\strip_{tag}_{wi}_{int(frac * 100)}.png"
            cv2.imwrite(tmp, big)
            res, _ = eng(tmp)
            texts = [x for _, x, _ in (res or [])][:8]
            marked = (verify_names.confirm_readings(tmp, texts)
                      if texts else [])
            print(f"  win {wi} ({a},{t},{c},{d}) strip {frac}: "
                  + (" | ".join(f"{x}{'' if ok else ' ?'}"
                                for x, ok in marked) or "(nothing read)"))
print("PROBE-DONE")
