import cv2, overlay, shapes, panes
img = cv2.imread(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-00.png")
print("overlay.windows", [[round(v) for v in r] for r in overlay.windows(img)])
print("shapes.windows ", [[round(v) for v in r] for r in shapes.windows(img)])
print("shapes.find    ", [[round(v) for v in r] for r in shapes.find(img)][:12])
print("_measured      ", panes._measured_windows(img))
