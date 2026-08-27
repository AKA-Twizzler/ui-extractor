import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import shapes, cv2
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
full = shapes._find_full(img)
print(len(full), "rectangles")
for r, g in sorted(full, key=lambda rg: rg[1])[:16]:
    print([round(v) for v in r], "gap", round(g), "area", round((r[2]-r[0])*(r[3]-r[1])/1e3), "k")
print("--- the ones on the left window's ground ---")
for r, g in full:
    if r[0] < 500 and r[2] > 1600 and r[1] < 520:
        print([round(v) for v in r], "gap", round(g))
