import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, numpy as np, machine
p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-03-00_pane4.png")
img = cv2.imread(p); print(img.shape)
med = np.median(img.reshape(-1,3), axis=0); print("bg", med)
per_y = np.median(img, axis=1)
d = np.abs(per_y - med).sum(axis=1)
ys = np.where(d > 40)[0]
groups=[]
for y in ys:
    if groups and y - groups[-1][1] <= 2: groups[-1][1]=y
    else: groups.append([y,y])
for g in groups: print(g, per_y[g[0]:g[1]+1].mean(axis=0).round(0))
