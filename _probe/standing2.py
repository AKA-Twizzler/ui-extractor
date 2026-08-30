import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, numpy as np
import overlay, machine, note_reader
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

CASES = [
    ("Claude Code For Beginners; Start Here", 328, "sticker PEOPLE"),
    ("Claude Code For Beginners; Start Here", 438, "sticker SOWE"),
    ("My AI Jarvis Makes Money. Here's How", 180, "room, must admit none"),
    ("Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26", 7979, "banner"),
    ("Live August 03", 540, "banner"),
]
print(f"{'case':34} {'p20':>5}{'p30':>5}{'p40':>5}{'p50':>5}{'p60':>5}   text / glyphs")
for title, secs, what in CASES:
    mp4 = sorted(glob.glob(os.path.join(machine.here(f"/mnt/g/Video/{title}"), "*.mp4")))[0]
    work = machine.here(f"/mnt/g/Images/{title}/_looks")
    paths = overlay.frames_across(mp4, secs, workdir=work)
    shots = [cv2.imread(p) for p in paths]
    shots = [s for s in shots if s is not None]
    if len(shots) < 3: continue
    stack = np.stack([s.astype(np.int16) for s in shots])
    change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
    ps = [float(np.percentile(change, q)) for q in (20, 30, 40, 50, 60)]
    got = overlay.standing_text(paths, engine=eng)
    line = "  ".join(f"{f['text']}={f['glyphs']:.0f}" for f in got) or "(none)"
    print(f"{what[:33]:34} " + "".join(f"{p:5.0f}" for p in ps) + f"   {line}")
