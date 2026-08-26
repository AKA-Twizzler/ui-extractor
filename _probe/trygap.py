import sys, cv2, numpy as np
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
h, w = img.shape[:2]
strip = cv2.cvtColor(img[0:64, :], cv2.COLOR_BGR2GRAY).astype(int)
for thr in (60, 90, 120):
    bright = (strip > thr).sum(axis=0) >= 2
    runs, x0, out = 0, None, []
    for x in range(w + 1):
        lit = x < w and bool(bright[x])
        if lit:
            if x0 is None: x0 = x
            runs = 0
        elif x0 is not None:
            runs += 1
            if runs >= 77 or x == w:
                if x - runs - x0 >= 40: out.append((x0, x - runs))
                x0, runs = None, 0
    print("thr", thr, "pieces", len(out), out[:8])
