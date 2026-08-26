import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import panes
for f in ("00-00-00", "00-02-50", "00-04-40"):
    img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png" % f)
    bs = panes.frame_regions(img)
    print(f, "panes", len(bs), "top strips", len([b for b in bs if b[1] == 0 and b[3] <= 70]))
