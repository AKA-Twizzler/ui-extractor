import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, checks, screenness, overlay
eng = checks.engine()
CASES = [("stjude","02:12:59","donation card, MUST keep"),
         ("aug03","00:09:00","livestream cards, MUST keep"),
         ("works","00:01:52","desktop + Finder"),
         ("jarvis","00:02:00","desktop, 7 panels")]
for key, stamp, what in CASES:
    p = checks.frame(key, stamp)
    img = cv2.imread(p)
    regs = screenness.ui_regions(img, eng)
    back = img.shape[1] / screenness.WORK_WIDTH
    boxes = [tuple(int(v * back) for v in r["box"]) for r in regs]
    pans = overlay.read_overlays(p, eng)["panels"]
    print(f"\n{what}   ui boxes {boxes}")
    for pn in pans:
        x0, y0, x1, y1 = pn["box"]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        inside = any(a <= cx < c and b <= cy < d for a, b, c, d in boxes)
        first = (pn["lines"] or [""])[0][:44]
        print(f"    centre ({cx},{cy}) inside_ui={inside}   {first!r}")
