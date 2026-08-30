import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, overlay, note_reader
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

def look(kind, title, secs):
    try:
        vid = sorted(glob.glob(f"G:/Video/{title}/*.mp4"))[0]
    except IndexError:
        print(f"  ??  no video for {title}"); return
    paths = overlay.frames_across(vid, secs, workdir=f"G:/Images/{title}/_looks")
    shots = [cv2.imread(p) for p in paths]
    shots = [s for s in shots if s is not None]
    if len(shots) < 3 or len({s.shape for s in shots}) != 1:
        print(f"  ??  {title[:26]} {secs}s: only {len(shots)} looks"); return
    stack = np.stack([s.astype(np.int16) for s in shots])
    change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
    still = float(np.percentile(change, 25))
    moving = float(np.percentile(change, overlay.STILLEST))
    res, _ = eng(paths[0])
    for box, text, _c in (res or []):
        x0 = int(min(q[0] for q in box)); x1 = int(max(q[0] for q in box))
        y0 = int(min(q[1] for q in box)); y1 = int(max(q[1] for q in box))
        if x1-x0 < 14 or y1-y0 < 8: continue
        g = cv2.cvtColor(shots[0][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        ink = note_reader.ink_mask(g)
        if ink.sum() < 25 or (~ink).sum() < 25: continue
        here = change[y0:y1, x0:x1]
        gl = float(np.median(here[ink])); gr = float(np.median(here[~ink]))
        if gr <= still or gl > gr or gl > moving:
            continue                       # what the reader admits today
        print(f"  {kind:8s} {gl/max(1.0,gr):5.2f}   glyphs={gl:6.1f} "
              f"ground={gr:6.1f}   {title[:20]:20s} {secs:5d}s  {text[:34]}")

ST = "Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26"
J31 = "Jarvis Raises Money for St. Judes with Epic Performance - Live Replay July 31, 2026"
for s in (3600, 7979, 10800, 14400):
    look("BANNER", ST, s)
for s in (900, 1800, 2700):
    look("BANNER", "Live August 03", s)
for s in (11880,):
    look("CAPTION", J31, s)
for s in (328, 438, 200):
    look("ROOM", "Claude Code For Beginners; Start Here", s)
for s in (181, 363, 544):
    look("ROOM", "How To Generate Leads With AI", s)
