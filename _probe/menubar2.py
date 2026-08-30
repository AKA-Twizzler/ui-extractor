"""The menu bar with both engines: do their first tokens agree?"""
import sys
import cv2
import numpy as np
import tempfile
import subprocess
import os

sys.path.insert(0, ".")
import machine

FRAMES = [
    ("works (Finder)",
     "G:/Images/How Claude Code Actually Works/00-07-29.png"),
    ("jarvis (chrome)",
     "G:/Images/My AI Jarvis Makes Money. Here's How/00-02-00.png"),
    ("obsidian",
     "G:/Images/How To Set Up Claude Code With Obsidian/00-02-09.png"),
    ("install (refuse)",
     "G:/Images/Install Claude Code and-or the AI Memory Vault/00-07-14.png"),
    ("memfiles (Finder)",
     "G:/Images/Move Memory Files Out of Claude Code Into Obsidian/"
     "00-00-00.png"),
    ("skills (refuse)",
     "G:/Images/How To Make Your Own AI Skills/00-01-30.png"),
]

from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

for tag, path in FRAMES:
    img = cv2.imread(path)
    if img is None:
        print(f"{tag}: MISSING")
        continue
    h = img.shape[0]
    band = img[0:max(24, int(h * 0.03))]
    big = machine.enlarge(band, 4)
    if float(np.median(big)) < 128:
        big = 255 - big
    res, _ = eng(big)
    rapid = []
    for b, t, _ in (res or []):
        rapid.append((min(p[0] for p in b), t.strip()))
    rapid.sort()
    rapid_join = " ".join(t for _, t in rapid)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        tmp = fh.name
    cv2.imwrite(tmp, big)
    r = subprocess.run([machine.tesseract_or_refuse(), tmp, "stdout",
                        "-l", "eng", "--psm", "7"],
                       capture_output=True, text=True, encoding="utf-8")
    os.unlink(tmp)
    tess = " ".join((r.stdout or "").split())
    print(f"{tag}\n   rapid: {rapid_join[:110]}\n   tess : {tess[:110]}")
