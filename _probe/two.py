import sys, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import checks, panes, overlay, shapes
for key, stamp in (("jarvis", "00:02:00"), ("works", "00:01:52")):
    p = checks.frame(key, stamp)
    img = cv2.imread(p)
    h, w = img.shape[:2]
    print("===", key, stamp, w, "x", h)
    print("   overlay:", [tuple(int(v) for v in r[:4]) for r in overlay.windows(img)])
    print("   shapes :", [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)])
    print("   windows:", panes._measured_windows(img))
    bs = panes.frame_regions(img, engine=checks.engine())
    print("   panes  :", len(bs))
    for b in bs:
        print("      ", b)
