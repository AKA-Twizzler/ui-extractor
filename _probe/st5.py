import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, numpy as np, machine
fr = cv2.imread(machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-03-00.png"))
crop = fr[880:965, 1785:1850]
big = cv2.resize(crop, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
cv2.imwrite(machine.here("/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/st5_crop.png"), big)
g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
ys, xs = np.where(g > 200)
print("bright box", xs.min(), ys.min(), xs.max(), ys.max())
