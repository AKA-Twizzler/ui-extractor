import sys, cv2, numpy as np
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import pytesseract
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
print("frame", img.shape)
for name, box, scale in [("left menu", (0, 0, 900, 46), 4),
                         ("right status", (2900, 0, 3840, 46), 4),
                         ("left menu 6x", (0, 0, 900, 46), 6)]:
    x0, y0, x1, y1 = box
    crop = img[y0:y1, x0:x1]
    big = cv2.resize(crop, (crop.shape[1]*scale, crop.shape[0]*scale), interpolation=cv2.INTER_LANCZOS4)
    g = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    for tag, im in (("grey", g), ("inv", 255 - g)):
        txt = pytesseract.image_to_string(im, config="--psm 7")
        print(f"  {name} [{tag}] -> {txt.strip()!r}")
