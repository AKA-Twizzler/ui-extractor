import sys, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import checks, panes, overlay, shapes
p = checks.frame("jarvis", "00:02:00")
img = cv2.imread(p); h, w = img.shape[:2]
print("frame", w, "x", h)
sh = [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)]
print("overlay:", [tuple(int(v) for v in r) for r in overlay.windows(img)])
print("shapes :", sh, [round(100.0*(r[2]-r[0])*(r[3]-r[1])/(w*h), 1) for r in sh])
print("panes now:", panes.frame_regions(img))
# what the same frame gives if a window is cut at its corridors too
import types
orig = panes.frame_regions
src = open(r"G:\AI\Ethereal\ui-extractor\panes.py", encoding="utf-8").read()
