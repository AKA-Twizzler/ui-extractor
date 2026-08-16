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

import overlay
import screenness
import machine

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


def pane_columns(img, engine=None, least=MIN_PANE):
    """The window's panes as (x0, x1) in working-size coordinates.

    `least` is the narrowest a pane may be, in those same coordinates. It has
    to be given when the picture is a WINDOW cut out of a frame rather than
    the frame: every picture is measured at one width, so a small window is
    magnified more than a large one, and a strip too thin to be a pane in the
    frame's own pixels is wide enough to pass in the window's. Left at its
    default it is the same test the frame gets, which is what a caller with a
    whole frame wants.
    """
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
        if e - last >= least:
            panes.append((last, e))
            last = e
    # What is left over at the right is too thin to be a pane of its own, and
    # it used to be dropped -- with whatever was written on it. On a card
    # reading "moonstone.co * 12k" the gap before the number is wide enough to
    # cut at, so the pane ended there and the number was never read by
    # anything. A strip too thin to stand alone belongs to its neighbour; it
    # does not belong to nobody.
    if panes:
        if w > last:
            panes[-1] = (panes[-1][0], w)
    else:
        panes = [(0, w)]
    return panes


def _free_spans(taken, least):
    """The stretches of a row of flags that are still false."""
    spans, start = [], None
    for x, t in enumerate(taken):
        if not t and start is None:
            start = x
        elif t and start is not None:
            if x - start >= least:
                spans.append((start, x))
            start = None
    if start is not None and len(taken) - start >= least:
        spans.append((start, len(taken)))
    return spans


def frame_regions(img, engine=None):
    """The rectangles of this frame to read, one at a time, in its own pixels.

    A frame is not always one window. Jared works across a whole desktop — a
    full-screen HUD on the left, the Clock app in the middle, a browser on the
    right — and split into vertical strips, as a single window is, the three
    run together: the menu bar came back as a folder tree with "Clock" and
    "File Edit" for folders, and everything else landed in one strip read as
    loose text.

    So the windows are found first, by their four drawn sides (overlay.py),
    and each is split into ITS panes rather than the frame's. What no window
    covers is the desktop, and it is split the same way it always was. A frame
    holding no window at all — every Obsidian, Finder and terminal frame in
    the fixtures — comes back exactly as it did before this existed.
    """
    h, w = img.shape[:2]
    scale = w / screenness.WORK_WIDTH
    boxes = []

    def split(crop, x_at, y_at, height):
        back = crop.shape[1] / screenness.WORK_WIDTH
        # a pane is thin or wide in the FRAME's pixels, never in the window's
        least = MIN_PANE * w / max(1, crop.shape[1])
        for a, b in pane_columns(crop, engine=engine, least=least):
            boxes.append((x_at + int(a * back), y_at,
                          x_at + int(b * back), y_at + height))

    found = overlay.windows(img)
    for x0, y0, x1, y1 in found:
        split(img[y0:y1, x0:x1], x0, y0, y1 - y0)

    taken = np.zeros(w, bool)
    for x0, _, x1, _ in found:
        taken[max(0, x0):min(w, x1)] = True
    for a, b in _free_spans(taken, max(1, int(MIN_PANE * scale))):
        split(img[:, a:b], a, 0, h)

    # A window takes its whole COLUMN out of the desktop, and what sits above
    # or below it in that column belonged to nothing at all. On a slide of nine
    # cards, one card was found as a window; the two cards beneath it fell in
    # its column, outside its height, and were in no region -- so "the tiny gem
    # * 4k" and "hearthstone * 15k" were read by nothing and reported nowhere.
    # The regions must cover the frame.
    for x0, y0, x1, y1 in found:
        for a, b in ((0, y0), (y1, h)):
            if b - a >= MIN_PANE * scale:
                split(img[a:b, x0:x1], x0, a, b - a)

    boxes.sort(key=lambda box: (box[0], box[1]))
    return boxes


def write_box(img, box, path, target=1400):
    """Cut a rectangle out of the ORIGINAL frame, not the shrunken copy.

    Boundaries are found on a small copy because that is cheap, but the pixels
    must come from the full-size frame. Cropping the small copy and enlarging
    it again destroys the fine text this exists to read — measured, it turned
    clean names into "Beyond the Baoics" and "Emall Gueue".
    """
    x0, y0, x1, y1 = box
    crop = img[max(0, y0):min(img.shape[0], y1),
               max(0, x0):min(img.shape[1], x1)]
    if crop.size == 0 or crop.shape[1] < 40:
        return None
    scale = max(1, int(target / crop.shape[1]))
    if scale > 1:
        crop = cv2.resize(crop, (crop.shape[1] * scale, crop.shape[0] * scale),
                          interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(path, crop)
    return crop


def write_pane(img, x0, x1, path, target=1400):
    """A full-height strip, named in working-size coordinates."""
    back = img.shape[1] / screenness.WORK_WIDTH
    return write_box(img, (int(x0 * back), 0, int(x1 * back), img.shape[0]),
                     path, target)


if __name__ == "__main__":
    import sys
    img = cv2.imread(sys.argv[1])
    for i, (a, b) in enumerate(pane_columns(img)):
        print(f"  pane {i}: x {a}-{b}  ({b-a} wide at working size)")
