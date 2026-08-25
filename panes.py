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
import os

import cv2
import numpy as np

import overlay
import screenness
import shapes
import machine

MIN_PANE = 90          # a pane narrower than this is furniture, not a pane
# How far a pane may be enlarged before it is handed to a reader. Every reader
# enlarges what it is given three times over AGAIN, so this number multiplies:
# without a cap a 139px sliver of a 1080p frame was magnified ten times here
# and three times again inside, and the reader was handed 4170 x 32400 pixels
# -- 135 million of them, five gigabytes of working memory, and the first video
# of a library sweep never finished.
#
# Three is where the fixtures stand. At two the tree loses a folder (30/31
# instead of 31/31 on folder-versus-file); at three every stage holds and the
# same sliver comes to 12 million pixels instead of 135. Past that the pixels
# are interpolated, not read, and only the memory grows.
MAX_SCALE = int(os.environ.get("PANE_MAX_SCALE", "3"))
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


def _measured_windows(img):
    """Every window on this frame, from both ways of measuring one.

    A window is a rectangle with four drawn sides (overlay.py) - but a
    window pushed off the side of the screen has only three, and a window
    whose sides fade across its title bar is found starting below its own
    head. shapes.py measures those too. Missing a window is what makes the
    reader take two windows standing side by side as one pane, and read
    their two lists as one table with the wrong words in every row.
    """
    got = []
    try:
        more = [tuple(int(round(v)) for v in r) for r in shapes.find(img)]
    except Exception:
        more = []

    def inside(a, b):
        """How much of a stands within b."""
        w = min(a[2], b[2]) - max(a[0], b[0])
        h = min(a[3], b[3]) - max(a[1], b[1])
        if w <= 0 or h <= 0:
            return 0.0
        return (w * h) / max(1.0, (a[2] - a[0]) * (a[3] - a[1]))

    # Only whole WINDOWS are added, never the panes inside them: a window is
    # cut into its own panes below, and adding its list and its sidebar as
    # windows too cuts the same ground three times over. On one frame that
    # turned two windows into forty-nine and the read took four minutes.
    more.sort(key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
    top = []
    for box in more:
        if box[2] - box[0] < 8 or box[3] - box[1] < 8:
            continue
        if any(inside(box, k) > 0.85 for k in top):
            continue
        top.append(box)
    for box in top:
        if not any(inside(box, k) > 0.8 and inside(k, box) > 0.8 for k in got):
            got.append(box)
    return got


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

    # The columns no window occupies at all are the desktop, and they are cut
    # the full height of the frame, exactly as they always were.
    least = max(1, int(MIN_PANE * scale))
    taken = np.zeros(w, bool)
    for x0, _, x1, _ in found:
        taken[max(0, x0):min(w, x1)] = True
    for a, b in _free_spans(taken, least):
        split(img[:, a:b], a, 0, h)

    # What is left is the frame above and below a window that does not run the
    # full height, and it used to belong to nothing at all: on a slide of nine
    # cards, one card was found as a window by its drawn sides, the two beneath
    # it fell in its column outside its height, and "the tiny gem * 4k" and
    # "hearthstone * 15k" were read by nothing and reported nowhere.
    #
    # So only THAT is added, inside the window columns and nowhere else. The
    # windows' own top and bottom edges cut those columns into bands; in one
    # band the set of columns a window holds does not change, so the free
    # spans of each band are rectangles which together cover the rest and
    # overlap neither each other nor the strips above.
    #
    #     |  strip  |   band above the window   |  strip  |
    #     |         +---------------------------+         |
    #     |         |          window           |         |
    #     |         +---------------------------+         |
    #     |         |   band below the window   |         |
    #
    # Adding a band per window instead covers the frame several times over,
    # and the same card came back in four panes. Cutting the WHOLE frame into
    # bands is worse still: the menu bar is a band 44 pixels tall, and taking
    # it out of the desktop strip changed which corridors that strip has --
    # one of the new ones ran straight through the Clock app's lap table.
    #
    # A band too short to hold a pane is not split into panes; it is read
    # whole, which is what the menu bar wants. Under eight pixels nothing
    # legible fits at all, and those are the sliver a rounded corner leaves.
    edges = sorted({0, h} | {y for _, y0, _, y1 in found for y in (y0, y1)})
    for top, bottom in zip(edges, edges[1:]):
        if bottom - top < 8:
            continue
        held = np.zeros(w, bool)
        for x0, y0, x1, y1 in found:
            if y0 < bottom and y1 > top:
                held[max(0, x0):min(w, x1)] = True
        # _free_spans returns the stretches that are FALSE, so the mask handed
        # to it is everything this band is NOT: held by a window here, or
        # outside the window columns entirely and already cut above.
        for a, b in _free_spans(held | ~taken, least):
            if bottom - top >= least:
                split(img[top:bottom, a:b], a, top, bottom - top)
            else:
                boxes.append((a, top, b, bottom))

    # A pane that runs across TWO windows reads their two lists as one
    # table, and every row of it comes out with one window's word in the
    # first cell and the other's in the second. Where a window's own side
    # stands inside a pane, that pane is cut there. Only those cuts are
    # added, so a frame keeps the panes it had and gains one where two
    # windows really do stand side by side in the same strip.
    sides = set()
    for wx0, _, wx1, _ in _measured_windows(img):
        sides.update((wx0, wx1))
    if sides:
        # a cut that would leave a sliver is not made: a strip too thin to
        # be a pane belongs to its neighbour, never to nobody
        least = max(8, int(MIN_PANE * scale / 2))
        cut = []
        for x0, y0, x1, y1 in boxes:
            marks = [x0]
            for x in sorted(x for x in sides if x0 < x < x1):
                if x - marks[-1] >= least and x1 - x >= least:
                    marks.append(x)
            marks.append(x1)
            for a, b in zip(marks, marks[1:]):
                cut.append((a, y0, b, y1))
        boxes = cut or boxes
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
    scale = min(MAX_SCALE, max(1, int(target / crop.shape[1])))
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
