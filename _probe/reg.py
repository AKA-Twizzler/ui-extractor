import sys, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import checks, panes, overlay, shapes
p = checks.frame("obsidian", "00:02:09")
img = cv2.imread(p)
print("frame", p, img.shape)
print("overlay.windows:", [tuple(int(v) for v in r) for r in overlay.windows(img)])
try:
    print("shapes.windows:", [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)])
except Exception as e:
    print("shapes.windows failed:", e)
print("_measured_windows:", panes._measured_windows(img))
bs = panes.frame_regions(img)
print("frame_regions ->", len(bs))
for b in bs:
    print("   ", b)
