#!/usr/bin/env python3
"""Split a window into its panes, so each is read as itself.

Why this has to be right: handed a whole window, the tree reader correctly
refuses, because a note's prose does not sit on the sidebar's row pitch. And
measuring text size across two panes at once mixes a sidebar's small labels
into a note's body and ruins the heading sizes.

A pane boundary shows up two ways and BOTH are needed:

  a drawn border   a line running the full height of the window, which no
                   text or icon ever does
  a gap in the     a vertical strip that no line of text crosses. Some layouts
  text             draw no border at all, and a plain ink threshold does not
                   find them either, because a note's own margins are not
                   empty — they carry background texture. Where the TEXT stops
                   is unambiguous, and it is what we actually care about.
"""
import cv2
import numpy as np

import screenness

MIN_PANE = 90          # a pane narrower than this is furniture, not a pane
EMPTY_BAND = 26        # an empty strip at least this wide separates panes
INK = 26               # how far from the local background a pixel counts as ink


def _ink_columns(work):
    """Per column: does this column hold any ink at all."""
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    k = np.ones((41, 1), np.uint8)
    lighter = cv2.subtract(g, cv2.morphologyEx(g, cv2.MORPH_OPEN, k))
    darker = cv2.subtract(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), g)
    ink = cv2.max(lighter, darker) > INK
    return ink.mean(axis=0)


def _borders(work):
    """Columns holding a line that runs the full height of the window."""
    g = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    k = np.ones((1, 41), np.uint8)
    lighter = cv2.subtract(g, cv2.morphologyEx(g, cv2.MORPH_OPEN, k))
    darker = cv2.subtract(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), g)
    cov = (cv2.max(lighter, darker) > 4).mean(axis=0)
    return [x for x, v in enumerate(cov) if v >= 0.75]


def text_gaps(work, engine, min_gap=40):
    """Vertical strips that no line of text crosses."""
    res, _ = engine(work)
    if not res:
        return [], []
    spans = [(int(min(p[0] for p in b)), int(max(p[0] for p in b)))
             for b, _, _ in res]
    covered = np.zeros(work.shape[1] + 1, bool)
    for a, b in spans:
        covered[max(0, a):min(len(covered), b + 1)] = True
    gaps, start = [], None
    for x in range(len(covered)):
        if not covered[x] and start is None:
            start = x
        elif covered[x] and start is not None:
            if x - start >= min_gap:
                gaps.append((start + x) // 2)
            start = None
    if start is not None and len(covered) - start >= min_gap:
        gaps.append((start + len(covered)) // 2)
    return gaps, spans


def pane_columns(img, engine=None):
    """The window's panes as (x0, x1) in working-size coordinates."""
    work = screenness.to_working_size(img)
    w = work.shape[1]
    cuts = set()

    for x in _borders(work):
        cuts.add(x)

    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    for x in text_gaps(work, engine)[0]:
        cuts.add(x)

    edges = [0] + sorted(cuts) + [w]
    panes, last = [], 0
    for e in edges[1:]:
        if e - last >= MIN_PANE:
            panes.append((last, e))
            last = e
    if w - last >= MIN_PANE:
        panes.append((last, w))
    return panes or [(0, w)]


def write_pane(img, x0, x1, path, target=1400):
    """Cut the pane out of the ORIGINAL frame, not the shrunken working copy.

    Boundaries are found on a small copy because that is cheap, but the pixels
    must come from the full-size frame. Cropping the small copy and enlarging
    it again destroys the fine text this exists to read — measured, it turned
    clean names into "Beyond the Baoics" and "Emall Gueue".
    """
    scale_back = img.shape[1] / screenness.WORK_WIDTH
    nx0, nx1 = int(x0 * scale_back), int(x1 * scale_back)
    pane = img[:, max(0, nx0):min(img.shape[1], nx1)]
    if pane.size == 0 or pane.shape[1] < 40:
        return None
    scale = max(1, int(target / pane.shape[1]))
    if scale > 1:
        pane = cv2.resize(pane, (pane.shape[1] * scale, pane.shape[0] * scale),
                          interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(path, pane)
    return pane


if __name__ == "__main__":
    import sys
    img = cv2.imread(sys.argv[1])
    for i, (a, b) in enumerate(pane_columns(img)):
        print(f"  pane {i}: x {a}-{b}  ({b-a} wide at working size)")
