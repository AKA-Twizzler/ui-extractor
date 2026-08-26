import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
from ui_geometry import tesseract_tsv
import machine
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
crop = img[0:64, 0:1036]
for pre in (1, 2, 4):
    a = machine.enlarge(crop, pre) if pre > 1 else crop
    b = machine.enlarge(a, 3)
    p = r"/home/trism/.claude/jobs/014c964f/tmp/replay\_probe\menu3.png"
    cv2.imwrite(p, b)
    rows = tesseract_tsv(p, psm=6)
    ws = [r["text"] for r in rows if (r.get("text") or "").strip()]
    print(f"pre={pre} total={pre*3}x: {' '.join(ws)[:80]}")
