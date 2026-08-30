"""Measure tie-density at pixel level on labelled areas of known frames.

The 6x8 grid is the named fault. Before replacing it, measure whether a
box-filtered tie map separates camera from screen at fine resolution, and at
what filter size. Boxes below were labelled by eye on the actual frames.
"""
import sys
import cv2
import numpy as np

sys.path.insert(0, ".")
import screenness

IMAGES = "G:/Images"

# (frame path, [(name, is_screen_or_None, (x0,y0,x1,y1) in native px)])
LABELLED = [
    (f"{IMAGES}/How Claude Code Actually Works/00-07-29.png", [
        ("finder_win", True,  (394, 163, 1747, 797)),
        ("terminal",   True,  (438, 858, 1972, 1939)),
        ("menubar",    True,  (0, 0, 3840, 40)),
        ("webcam",     False, (2669, 1142, 3763, 2074)),
        ("wall_left",  False, (58, 826, 365, 2074)),
        ("wall_mid",   False, (1997, 230, 2266, 1075)),
        ("icon_field", None,  (2035, 115, 3706, 998)),
    ]),
    (f"{IMAGES}/Jarvis and Jaredrhod Raise Money for St. Jude's Children's "
     f"Hospital - Live Replay 8-1-26/02-12-59.png", [
        ("room_left",  False, (200, 100, 650, 700)),
        ("face",       False, (750, 300, 1150, 800)),
        ("card",       True,  (95, 905, 790, 1020)),
        ("banner",     True,  (880, 935, 1210, 985)),
        ("chat",       None,  (1300, 750, 1900, 1020)),
    ]),
    (f"{IMAGES}/Claude Code For Beginners; Start Here/00-05-28.png", [
        ("whole_head", False, None),
    ]),
    (f"{IMAGES}/How To Set Up Claude Code With Obsidian/00-02-09.png", [
        ("whole_obsi", True, None),
    ]),
    (f"{IMAGES}/My AI Jarvis Makes Money. Here's How/00-02-00.png", [
        ("whole_hud",  True, None),
    ]),
]


def density(work, k):
    ties = screenness.tie_map(work).astype(np.float32)
    return cv2.boxFilter(ties, -1, (k, k), normalize=True)


def main():
    for k in (25, 41, 61):
        print(f"\n================ filter {k}x{k} (working width "
              f"{screenness.WORK_WIDTH}) ================")
        for path, boxes in LABELLED:
            bgr = cv2.imread(path)
            if bgr is None:
                print(f"  MISSING {path}")
                continue
            native_w = bgr.shape[1]
            work = screenness.to_working_size(bgr)
            d = density(work, k)
            s = screenness.WORK_WIDTH / native_w
            short = path.split("/")[-2][:28]
            for name, is_screen, box in boxes:
                if box is None:
                    patch = d
                else:
                    x0, y0, x1, y1 = [int(v * s) for v in box]
                    patch = d[y0:y1, x0:x1]
                if patch.size == 0:
                    print(f"  {short:28} {name:11} EMPTY")
                    continue
                p10, p50, p90 = np.percentile(patch, (10, 50, 90))
                above = float((patch >= 0.55).mean())
                tag = {True: "screen", False: "camera", None: "  ??  "}[is_screen]
                print(f"  {short:28} {name:11} {tag}  "
                      f"p10 {p10:.2f}  p50 {p50:.2f}  p90 {p90:.2f}  "
                      f">=0.55 {above * 100:5.1f}%")


if __name__ == "__main__":
    main()
