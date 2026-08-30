import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import screenness
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
CASES = [
    ("How Claude Code Actually Works/00-01-52.png", "desktop + Finder, must be UI"),
    ("How Claude Code Actually Works/00-03-44.png", "desktop + empty zsh"),
    ("My AI Jarvis Makes Money. Here's How/00-02-00.png", "desktop, must be UI"),
    ("Jarvis and Jaredrhod Raise Money for St. Jude's Children's Hospital - Live Replay 8-1-26/02-12-59.png", "live room, must be low"),
    ("Claude Code For Beginners; Start Here/00-05-28.png", "talking head, must be 0"),
]
for rel, what in CASES:
    p = os.path.join("G:\\Images", rel.replace("/", "\\"))
    img = cv2.imread(p)
    if img is None:
        print(f"-- missing {rel}"); continue
    for mc in (1, 2):
        regs = screenness.ui_regions(img, eng, min_cells=mc)
        share = sum(r["share"] for r in regs) * 100
        print(f"{what[:32]:34} min_cells={mc}  regions={len(regs):2d}  "
              f"share={share:5.1f}%")
