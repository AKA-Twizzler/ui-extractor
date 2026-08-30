"""Every box a picture draws, set against the rectangles the real frame has.

A window is a rectangle on the screen. If the drawing puts a box where the
frame has no rectangle near it, the box is in the wrong place or the wrong
size, and no amount of looking at the note itself would say so.
"""
import os, re, sys
sys.path.insert(0, "/mnt/g/AI/Ethereal/ui-extractor")
import selfcheck as SC
import shapes
from PIL import Image

NOTE = sys.argv[1]
FRAMES = sys.argv[2]

def iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    ua = (ax1-ax0)*(ay1-ay0) + (bx1-bx0)*(by1-by0) - inter
    return inter / max(1e-6, ua)

lines = open(NOTE, encoding="utf-8").read().split("\n")
for k, ln in enumerate(lines, 1):
    if not SC.BLOCK.match(ln):
        continue
    st = re.search(r'class="sn-stamp">(\d\d:\d\d:\d\d)', ln)
    if not st:
        continue
    f = os.path.join(FRAMES, st.group(1).replace(":", "-") + ".png")
    if not os.path.exists(f):
        print(st.group(1), "no frame on disk"); continue
    W, H = Image.open(f).size
    real = [[100*r[0]/W, 100*r[1]/H, 100*r[2]/W, 100*r[3]/H] for r in shapes.find(f)]
    tags = re.findall(r'class="sn-ghost-tag"[^>]*>([^<]*)<', ln)
    got = []
    for i, (p, c) in enumerate(SC._boxes(ln, "sn-ghost")):
        got.append(("outline " + (tags[i] if i < len(tags) else "?")[:24], p))
    for p, c in SC._boxes(ln, "sn-slot"):
        got.append(("FILLED", p))
    print("===", st.group(1), f"| {len(real)} rectangles on the frame")
    for name, p in got:
        box = [p[0], p[1], p[0]+p[2], p[1]+p[3]]
        best = max((iou(box, r) for r in real), default=0.0)
        near = max(real, key=lambda r: iou(box, r), default=None)
        mark = "ok  " if best >= 0.55 else ("near" if best >= 0.3 else "OFF ")
        s = ("  best %5.2f  -> %5.1f %5.1f %5.1f %5.1f" %
             (best, near[0], near[1], near[2]-near[0], near[3]-near[1])) if near else ""
        print("   %s %-34s l %5.1f t %5.1f w %5.1f h %5.1f%s" %
              (mark, name, p[0], p[1], p[2], p[3], s))
