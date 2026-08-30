"""Which cut splits the Finder table, and what distinguishes it?

Candidate rule: a text-gap is a table's column gutter, not a pane boundary,
when the text LINES beside it continue across -- a box ending before the gap
and a box starting after it, sharing the same y band. A table's 16 rows all
continue; a sidebar and a note beside it line up only by chance.

Truth to hit:
  works 00:07:29  the Finder window must stay one pane (its gap crossed by rows)
  obsidian 00:02:09  the frame must still split (sidebar | note)
"""
import sys
import cv2
import numpy as np

sys.path.insert(0, ".")
import overlay
import panes
import screenness

from rapidocr_onnxruntime import RapidOCR
ENG = RapidOCR()


def lines_of(res):
    rows = []
    for b, t, _ in (res or []):
        x0 = min(p[0] for p in b); x1 = max(p[0] for p in b)
        y0 = min(p[1] for p in b); y1 = max(p[1] for p in b)
        rows.append((x0, x1, y0, y1, t))
    return rows


def crossing(rows, x):
    """How many text lines continue across x, and how many touch it at all."""
    left = [r for r in rows if r[1] <= x]
    right = [r for r in rows if r[0] >= x]
    cross = 0
    for lx0, lx1, ly0, ly1, _ in left:
        for rx0, rx1, ry0, ry1, _ in right:
            over = min(ly1, ry1) - max(ly0, ry0)
            if over > 0.5 * min(ly1 - ly0, ry1 - ry0):
                cross += 1
                break
    beside = len(left)
    return cross, beside


def report(tag, crop):
    work = screenness.to_working_size(crop)
    print(f"\n=== {tag}: working {work.shape[1]}x{work.shape[0]} ===")
    print(f"  border cuts: {panes._borders(work)}")
    res, _ = ENG(work)
    gaps, _spans = panes.text_gaps(work, lambda im: (res, None))
    rows = lines_of(res)
    print(f"  text-gap cuts at {gaps}; {len(rows)} text boxes")
    for x in gaps:
        c, b = crossing(rows, x)
        print(f"    gap at x={x}: {c} of {b} left-side lines continue across")


img = cv2.imread("G:/Images/How Claude Code Actually Works/00-07-29.png")
wins = overlay.windows(img)
print(f"works windows: {wins}")
for i, (x0, y0, x1, y1) in enumerate(wins):
    report(f"works window {i}", img[y0:y1, x0:x1])

img = cv2.imread("G:/Images/How To Set Up Claude Code With Obsidian/"
                 "00-02-09.png")
print(f"\nobsidian windows: {overlay.windows(img)}")
report("obsidian whole frame", img)
