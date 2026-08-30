import sys; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2, numpy as np, machine, style_reader as sr
fr = cv2.imread(machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-03-00.png"), cv2.IMREAD_GRAYSCALE)
for s in (32, 40, 48, 56, 64):
    t = sr._arrow(s)
    for name, tt in (("dark", t), ("light", 255 - t)):
        res = cv2.matchTemplate(fr, tt, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        print(s, name, round(val, 3), loc)
