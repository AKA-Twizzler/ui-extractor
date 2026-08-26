import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, panes, overlay, shapes, screenness
p = checks.frame("memfiles", "00:00:00")
img = cv2.imread(p); h, w = img.shape[:2]
print("frame", w, "x", h)
print("shapes:", [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)])
bs = panes.frame_regions(img)
print("panes:", len(bs))
for i, b in enumerate(bs):
    print("   [%d]" % i, b)
# is the sidebar|list divider drawn inside the big window?
x0, y0, x1, y1 = 184, 472, 1760, 1140
crop = img[y0:y1, x0:x1]
work = screenness.to_working_size(crop)
print("borders inside the left window (working units, width %d):" % work.shape[1], panes._borders(work))
