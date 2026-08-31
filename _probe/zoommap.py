"""The measured zoom used as a MAP OF PLACE, checked on a window's own corner.

The same Finder window stands on two frames at two zooms. Carry its rectangle
from the zoomed frame back onto the unzoomed one with nothing but the measured
crops, and its top-left corner must land on the corner the unzoomed frame's own
reading recorded. Nothing here reads a word.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import zoom

IMG = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
W, H = 3840, 2160
BASE = "00-00-00"
CASES = [("00-00-30", [88, 272, 2372, 1680], [773, 472, 1748, 1140]),
         ("00-01-30", [96, 272, 2376, 1612], [773, 472, 1748, 1140])]

b = zoom.measure(os.path.join(IMG, BASE + ".png"), os.path.join(IMG, BASE + ".png"))
print("base %s: scale %.2f at (%.2f, %.2f)" % (BASE, b[0], b[1], b[2]))
for name, wb, want in CASES:
    a = zoom.measure(os.path.join(IMG, name + ".png"), os.path.join(IMG, BASE + ".png"))
    k = b[0] / a[0]
    dx = (W / a[0]) * (b[1] - a[1])
    dy = (H / a[0]) * (b[2] - a[2])
    back = [(wb[0] - dx) / k, (wb[1] - dy) / k, (wb[2] - dx) / k, (wb[3] - dy) / k]
    print("%s: scale %.2f  ->  zoom %.2f, shift (%.0f, %.0f)" % (name, a[0], k, dx, dy))
    print("    window %s carried back to (%.0f, %.0f); its own reading says (%d, %d)"
          % (wb[:2], back[0], back[1], want[0], want[1]))
    print("    off by %.0f px across and %.0f px down, on a %d-wide screen"
          % (abs(back[0] - want[0]), abs(back[1] - want[1]), W))
