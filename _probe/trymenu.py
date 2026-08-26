import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
from ui_geometry import tesseract_tsv
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
print("frame", img.shape)
for name, box, scale, psm in [("left 4x psm7", (0, 0, 900, 46), 4, 7),
                              ("left 4x psm6", (0, 0, 900, 46), 4, 6),
                              ("left 6x psm7", (0, 0, 900, 46), 6, 7),
                              ("right 4x psm7", (2900, 0, 3840, 46), 4, 7)]:
    x0, y0, x1, y1 = box
    crop = img[y0:y1, x0:x1]
    big = cv2.resize(crop, (crop.shape[1]*scale, crop.shape[0]*scale), interpolation=cv2.INTER_LANCZOS4)
    p = r"/home/trism/.claude/jobs/014c964f/tmp/replay\_probe\menu.png"
    cv2.imwrite(p, big)
    rows = tesseract_tsv(p, psm=psm)
    words = [r["text"] for r in rows if (r.get("text") or "").strip() and float(r.get("conf", -1) or -1) > 40]
    print(f"  {name}: {' | '.join(words)}")
