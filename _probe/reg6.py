import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, panes, overlay, shapes
p = checks.frame("memfiles", "00:00:00")
img = cv2.imread(p)
print("overlay:", [tuple(int(v) for v in r[:4]) for r in overlay.windows(img)])
print("shapes :", [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)])
print("measured:", panes._measured_windows(img))
