import sys, os, glob, re
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2
import overlay, screenness

from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()

# every full frame the sweep already captured, so nothing is re-decoded
frames = []
for d in sorted(glob.glob(r"G:\Images\*")):
    if not os.path.isdir(d) or os.path.basename(d).startswith("_"):
        continue
    for p in sorted(glob.glob(os.path.join(d, "??-??-??.png"))):
        frames.append(p)

print("%d captured frames on disk" % len(frames))

def by_box(regions, panels, width):
    back = width / screenness.WORK_WIDTH
    boxes = [tuple(int(v * back) for v in r["box"]) for r in regions]
    out = []
    for panel in panels:
        x0, y0, x1, y1 = panel["box"]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        if not any(a <= cx < c and b <= cy < d for a, b, c, d in boxes):
            out.append(panel)
    return out

changed = 0
looked = 0
for p in frames:
    img = cv2.imread(p)
    if img is None:
        continue
    try:
        got = overlay.read_overlays(p, eng)
    except Exception as e:
        continue
    panels = got.get("panels") or []
    if not panels:
        continue
    looked += 1
    regions = screenness.ui_regions(img, eng) or []
    old = by_box(regions, panels, img.shape[1])
    new = overlay.floating(panels, regions, img.shape[1], screenness.WORK_WIDTH)
    if len(old) != len(new):
        changed += 1
        print("  %s" % p)
        print("    panels %d   kept before %d   kept now %d"
              % (len(panels), len(old), len(new)))
        oldset = set(id(x) for x in old)
        for panel in new:
            if id(panel) not in oldset:
                lines = " | ".join((panel.get("lines") or [])[:3])
                print("      now reported as drawn on the picture: %s" % lines[:90])

print("looked at %d frames carrying panels; %d changed" % (looked, changed))
