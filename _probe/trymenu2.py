import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
from ui_geometry import tesseract_tsv
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
for h in (44, 46, 52, 64):
    for psm in (6, 7):
        crop = img[0:h, 0:1036]
        big = cv2.resize(crop, (crop.shape[1]*4, crop.shape[0]*4), interpolation=cv2.INTER_LANCZOS4)
        p = r"/home/trism/.claude/jobs/014c964f/tmp/replay\_probe\menu2.png"
        cv2.imwrite(p, big)
        rows = tesseract_tsv(p, psm=psm)
        ws = [r["text"] for r in rows if (r.get("text") or "").strip()]
        print(f"h={h} psm={psm}: {' '.join(ws)[:90]}")
