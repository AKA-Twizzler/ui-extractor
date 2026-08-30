import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, overlay

worst = []
for png in sorted(glob.glob("G:/Images/Install Claude Code*/*.png"))[:40]:
    if "_" in os.path.basename(png):
        continue
    bgr = cv2.imread(png)
    if bgr is None:
        continue
    h, w = bgr.shape[:2]
    for x0, y0, x1, y1 in overlay.panels(bgr):
        mp = (x1 - x0) * (y1 - y0) * 9 / 1e6
        worst.append((mp, f"{mp:7.1f} Mpx after 3x   frame {w}x{h}   "
                          f"panel {x1-x0}x{y1-y0}  {os.path.basename(png)}"))
for _, line in sorted(worst, reverse=True)[:12]:
    print(line)
