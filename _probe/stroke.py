"""What the stroke-measured enlargement would decide, across the library.

Stroke width: median run length of ink, both directions, runs never crossing
rows. A native UI stroke is 1.5-2.5px, so times-3 lands it at 4.5-7.5 -- the
range every fixture passes in. Target 6: times = ceil(6 / stroke), capped at
what the caller asked. A pane the splitter already widened arrives with fat
strokes and stops being enlarged again, which is the whole memory fix.
"""
import glob
import sys
import cv2
import numpy as np

sys.path.insert(0, ".")

INK = 26


def stroke_px(img, step=2):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = g[::step, ::step]
    k = np.ones((31, 1), np.uint8)
    lighter = cv2.subtract(g, cv2.morphologyEx(g, cv2.MORPH_OPEN, k))
    kt = np.ones((1, 31), np.uint8)
    darker = cv2.subtract(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), g)
    ink = cv2.max(lighter, darker) > INK
    lens = []
    for arr in (ink, ink.T):
        pad = np.zeros((arr.shape[0], 1), bool)
        flat = np.hstack([pad, arr, pad]).ravel()
        d = np.diff(flat.astype(np.int8))
        starts = np.flatnonzero(d == 1)
        ends = np.flatnonzero(d == -1)
        lens.append(ends - starts)
    lens = np.concatenate(lens)
    if len(lens) < 50:
        return None
    return float(np.median(lens)) * step


paths = sorted(glob.glob("G:/Images/*/*_pane*.png"))
paths = [p for p in paths if "_3x" not in p and "panel" not in p]
print(f"{len(paths)} stored panes")
times = {1: 0, 2: 0, 3: 0}
none = 0
saved = 0.0
kept = 0.0
for p in paths:
    img = cv2.imread(p)
    if img is None:
        continue
    s = stroke_px(img)
    mpx = img.shape[0] * img.shape[1] / 1e6
    if s is None:
        t = 3
        none += 1
    else:
        t = min(3, max(1, int(np.ceil(6.0 / s))))
    times[t] += 1
    saved += mpx * (9 - t * t)
    kept += mpx * t * t
print(f"no measurable stroke (falls back to 3): {none}")
print(f"times chosen: {times}")
print(f"pixels handed to readers: {kept:.0f} Mpx instead of "
      f"{kept + saved:.0f} Mpx")

for p in paths[:6] + paths[-3:]:
    img = cv2.imread(p)
    if img is None:
        continue
    s = stroke_px(img)
    print(f"  {p.split(chr(92))[-1][:44]:46} stroke "
          f"{s if s else -1:5.1f}  {img.shape[1]}x{img.shape[0]}")
