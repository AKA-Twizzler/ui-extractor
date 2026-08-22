import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, numpy as np, machine
fr = cv2.imread(machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-03-00.png"), cv2.IMREAD_GRAYSCALE)
t = fr[894:950, 1798:1833]
cv2.imwrite(machine.here("/home/trism/.claude/jobs/014c964f/tmp/replay/pointer.png"), t)
print("template", t.shape)
# match on this frame and on the other frame at a few scales
for name in ("00-03-00.png", "00-04-10.png", "00-01-20.png"):
    p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/" + name)
    g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if g is None: print(name, "missing"); continue
    for sc in (0.5, 0.75, 1.0, 1.25, 1.5):
        tt = cv2.resize(t, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(g, tt, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        # second best away from the first
        res2 = res.copy(); y, x = loc[1], loc[0]
        res2[max(0,y-30):y+30, max(0,x-30):x+30] = 0
        _, val2, _, _ = cv2.minMaxLoc(res2)
        print(name, sc, round(val, 3), loc, "next", round(val2, 3))
