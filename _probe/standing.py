import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np
import overlay, machine, note_reader
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

CASES = [
    ("Claude Code For Beginners; Start Here", 328),
    ("Claude Code For Beginners; Start Here", 438),
    ("Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26", 7979),
    ("Live August 03", 540),
]
for title, secs in CASES:
    mp4 = sorted(glob.glob(os.path.join(machine.here(f"/mnt/g/Video/{title}"), "*.mp4")))[0]
    work = machine.here(f"/mnt/g/Images/{title}/_looks")
    paths = overlay.frames_across(mp4, secs, workdir=work)
    shots = [cv2.imread(p) for p in paths]
    shots = [s for s in shots if s is not None]
    if len(shots) < 3:
        print(f"{title[:34]:34s} @{secs}: only {len(shots)} looks"); continue
    stack = np.stack([s.astype(np.int16) for s in shots])
    change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
    still = float(np.percentile(change, 25))
    moving = float(np.median(change))
    p75 = float(np.percentile(change, 75))
    print(f"\n== {title[:44]} @{secs}s   still(p25)={still:.0f} "
          f"median={moving:.0f} p75={p75:.0f}")
    for f in overlay.standing_text(paths, engine=eng):
        print(f"    ADMITTED {f['text']!r:26} glyphs={f['glyphs']:.0f} "
              f"ground={f['ground']:.0f}")
