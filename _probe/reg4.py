import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, panes, overlay, shapes
p = checks.frame("skills", "00:01:00")
img = cv2.imread(p); h, w = img.shape[:2]
print("frame", w, "x", h)
sh = [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)]
print("overlay:", [tuple(int(v) for v in r) for r in overlay.windows(img)])
print("shapes :", sh, [round(100.0*(r[2]-r[0])*(r[3]-r[1])/(w*h), 1) for r in sh])
bs = panes.frame_regions(img)
print("panes:", len(bs))
for i, b in enumerate(bs):
    print("   [%d]" % i, b)
