"""Are a stationary window's rectangles the SAME rectangle from moment to
moment?  Sets the identity rule for carrying a window's words forward."""
import glob
import re
import sys

import cv2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import overlay

DIRS = [
    r"G:\Images\How Claude Code Actually Works",
    r"G:\Images\How I Trained My AI To Stop Making Mistakes",
    r"G:\Images\Why Your AI Repeats The Same Mistake",
    r"G:\Images\Live August 03",
    r"G:\Images\How To Set Up Claude Code With Obsidian",
    r"G:\Images\A Look Inside My Million Dollar AI Business",
]
for d in DIRS:
    frames = [p for p in sorted(glob.glob(d + r"\*.png"))
              if re.search(r"\\\d\d-\d\d-\d\d\.png$", p)]
    print("==", d.split("\\")[-1], f"({len(frames)} frames)")
    for p in frames:
        img = cv2.imread(p)
        if img is None:
            continue
        wins = overlay.windows(img) or []
        if wins:
            print("  ", p.split("\\")[-1], wins)
print("PROBE-DONE")
