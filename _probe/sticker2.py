import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np, overlay, note_reader
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

def look(title, secs, want):
    vid = sorted(glob.glob(f"G:/Video/{title}/*.mp4"))[0]
    paths = overlay.frames_across(vid, secs, workdir=f"G:/Images/{title}/_looks")
    shots = [cv2.imread(p) for p in paths]
    shots = [s for s in shots if s is not None]
    stack = np.stack([s.astype(np.int16) for s in shots])
    change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
    pct = {p: float(np.percentile(change, p)) for p in (10, 20, 25, 30, 40, 50)}
    res, _ = eng(paths[0])
    print(f"\n{title[:34]:34s} {secs}s   {len(shots)} looks   "
          + " ".join(f"p{k}={v:.0f}" for k, v in pct.items()))
    for box, text, _c in (res or []):
        if want and not any(w.lower() in text.lower() for w in want):
            continue
        x0 = int(min(q[0] for q in box)); x1 = int(max(q[0] for q in box))
        y0 = int(min(q[1] for q in box)); y1 = int(max(q[1] for q in box))
        if x1-x0 < 14 or y1-y0 < 8: continue
        g = cv2.cvtColor(shots[0][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        ink = note_reader.ink_mask(g)
        if ink.sum() < 25 or (~ink).sum() < 25: continue
        here = change[y0:y1, x0:x1]
        gl = float(np.median(here[ink])); gr = float(np.median(here[~ink]))
        print(f"    glyphs={gl:6.1f}  ground={gr:6.1f}  g/gr={gl/max(1,gr):4.2f}"
              f"  g/p40={gl/max(1,pct[40]):4.2f}   {text[:40]}")

look("How To Generate Leads With AI", 181, ["WQHD"])
look("How To Generate Leads With AI", 363, ["Hat"])
look("Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26", 7979, ["jaredrhod"])
look("Live August 03", 1800, ["jaredrhod", "aug"])
