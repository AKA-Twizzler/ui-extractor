import sys, cv2
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import checks, panes, overlay, shapes
for key, stamp in (("obsidian", "00:06:00"), ("works", "00:07:00"), ("obsidian", "00:07:30")):
    p = checks.frame(key, stamp)
    img = cv2.imread(p)
    h, w = img.shape[:2]
    ov = [tuple(int(v) for v in r) for r in overlay.windows(img)]
    sh = [tuple(int(v) for v in r[:4]) for r in shapes.windows(img)]
    bs = panes.frame_regions(img)
    print(f"== {key} {stamp}  frame {w}x{h}")
    print("   overlay:", ov)
    print("   shapes :", sh, [round(100.0*(r[2]-r[0])*(r[3]-r[1])/(w*h), 2) for r in sh])
    print("   panes  :", len(bs))
    for i, b in enumerate(bs):
        print("      [%d]" % i, b)
