import sys; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2, machine
fr = cv2.imread(machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-04-10.png"))
crop = fr[900:980, 290:370]
cv2.imwrite(machine.here("/mnt/g/AI/Ethereal/ui-extractor/_probe/st7_crop.png"), cv2.resize(crop, None, fx=5, fy=5, interpolation=cv2.INTER_NEAREST))
print("ok")
