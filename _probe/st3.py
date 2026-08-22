import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, machine
fr = cv2.imread(machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-03-00.png"))
crop = fr[700:1100, 1298:2500]
cv2.imwrite(machine.here("/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/st3_crop.png"), crop)
print("ok", crop.shape)
