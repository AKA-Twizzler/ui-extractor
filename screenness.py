#!/usr/bin/env python3
"""Find interface anywhere in a frame, and say where it is.

The question answered here is "is there UI on this frame, and whereabouts" —
never "what application is it", and never "is this a screen recording". A
camera pointed at the real world with a caption bar, a phone overlay, or a
monitor in shot HAS interface and is worth capturing; a camera pointed at a
person with nothing on it does not. Nothing is read, so it runs fast enough over a whole
video, and it works on any interface in any language, including ones nobody
has seen before.

The measurement, and why it is this one:

  A camera sensor puts noise on every pixel, so two neighbouring pixels are
  almost never EXACTLY equal. A screen paints its flat areas with one exact
  value, so most neighbours are. Counting exact ties separates them cleanly,
  measured on labelled frames from two of Jared's videos:

      camera   0.387  0.412  0.464  0.467
      screen   0.495  0.665  0.666  0.747  0.765  0.778  0.893

  Three other candidates were tried and dropped for not separating: local
  flatness overlapped, edge squareness put a camera frame at the very top, and
  palette size did not order the two groups at all.

The frame is scored in a grid of cells, so a screen recording with a webcam
bubble, or a phone video with a caption bar, reports which PARTS are interface
instead of one blurred average that is right about neither.
"""
import cv2
import numpy as np
import machine

GRID = (6, 8)          # rows, cols of cells the frame is scored in
CELL_IS_SCREEN = 0.55  # a cell's tie-fraction above this reads as interface
SURE_CAMERA = 0.08     # below this share of cells, certainly a camera
SURE_SCREEN = 0.35     # above this share of cells, certainly a screen
WORK_WIDTH = 1280      # the measure is made at a fixed size, never native

# The size matters and is not a detail. At native 4K, heavy compression paints
# camera footage in flat blocks of identical value and it scores like a screen;
# a camera frame measured 33% at 4K and 10% at this width. Everything is
# measured at one working width so the numbers mean the same thing every time.


def tie_map(bgr):
    """Per pixel: is it exactly equal to the neighbour on its right or below."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
    hor = np.zeros(g.shape, bool)
    ver = np.zeros(g.shape, bool)
    hor[:, :-1] = np.diff(g, axis=1) == 0
    ver[:-1, :] = np.diff(g, axis=0) == 0
    return hor & ver


def cell_scores(bgr):
    """Score every cell of the frame from 0 (camera) to 1 (screen)."""
    ties = tie_map(bgr).astype(np.float32)
    h, w = ties.shape
    rows, cols = GRID
    out = np.zeros(GRID, np.float32)
    for r in range(rows):
        y0, y1 = r * h // rows, (r + 1) * h // rows
        for c in range(cols):
            x0, x1 = c * w // cols, (c + 1) * w // cols
            out[r, c] = float(ties[y0:y1, x0:x1].mean())
    return out


def screen_fraction(bgr):
    """How much of the frame is interface, and the map that says where."""
    s = cell_scores(bgr)
    return float((s >= CELL_IS_SCREEN).mean()), s


def to_working_size(bgr):
    if bgr.shape[1] == WORK_WIDTH:
        return bgr
    h = int(bgr.shape[0] * WORK_WIDTH / bgr.shape[1])
    return cv2.resize(bgr, (WORK_WIDTH, h), interpolation=cv2.INTER_AREA)


def verdict(bgr):
    """'screen', 'camera', or 'uncertain' — plus how much and where.

    Deliberately three answers, not two. Most frames are obviously one or the
    other and cost almost nothing to settle. The few in between are handed to
    a slower, surer test rather than forced into a guess here, which is what
    keeps a small interface in the corner of a camera shot from being thrown
    away as noise.
    """
    frac, s = screen_fraction(to_working_size(bgr))
    if frac <= SURE_CAMERA:
        return "camera", frac, s
    if frac >= SURE_SCREEN:
        return "screen", frac, s
    return "uncertain", frac, s


def has_interface(bgr):
    v, frac, s = verdict(bgr)
    return v != "camera", frac, s


def picture(scores):
    """The cells as a small picture: # interface, + borderline, . camera."""
    return "\n".join("".join("#" if v >= CELL_IS_SCREEN else
                             ("+" if v >= CELL_IS_SCREEN - 0.08 else ".")
                             for v in row) for row in scores)


def clusters(mask):
    """Connected groups of interface-looking cells, as (cells, r0, r1, c0, c1)."""
    rows, cols = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for r in range(rows):
        for c in range(cols):
            if not mask[r, c] or seen[r, c]:
                continue
            stack, cells = [(r, c)], []
            seen[r, c] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < rows and 0 <= nx < cols and mask[ny, nx] \
                            and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            ys = [y for y, _ in cells]
            xs = [x for _, x in cells]
            out.append((len(cells), min(ys), max(ys), min(xs), max(xs)))
    out.sort(reverse=True)
    return out


def candidate_regions(bgr, min_cells=2):
    """Where interface COULD be, from pixels alone. No reading, no engine.

    Separated out so a whole video can be segmented before anything is read.
    Reading is the expensive step and most of it is redundant: inside a long
    stretch of one screen, confirming every sample tells you nothing the first
    one did not.
    """
    work = to_working_size(bgr)
    cells = cell_scores(work)
    h, w = work.shape[:2]
    rows, cols = GRID
    out = []
    for n, r0, r1, c0, c1 in clusters(cells >= CELL_IS_SCREEN):
        if n < min_cells:
            continue
        out.append({"cells": n, "share": n / (rows * cols),
                    "box": (c0 * w // cols, r0 * h // rows,
                            (c1 + 1) * w // cols, (r1 + 1) * h // rows)})
    return out


def rows_aligned(boxes, tol=6, need=3):
    """Do these text boxes line up the way interface does.

    Interface stacks its text in columns that share a left edge — a tree, a
    list, a menu, a form. Writing in the real world does not: a sign, a book
    spine, a whiteboard scrawl gives you one or two strings at odd positions.
    Without this test, flat-plus-text calls a printed sign an interface.
    """
    xs = sorted(int(min(p[0] for p in b)) for b, _, _ in boxes)
    best = run = 1
    for a, b in zip(xs, xs[1:]):
        run = run + 1 if b - a <= tol else 1
        best = max(best, run)
    return best >= need


def ui_regions(bgr, engine, min_cells=2, min_boxes=5):
    """Regions of the frame that hold interface, confirmed by finding text.

    A flat, hard-edged patch alone is not interface — a painted wall is flat
    too. What makes it interface is that it CARRIES TEXT. So the cheap pixel
    test proposes the regions and a read of that region alone confirms them,
    which is both surer and far cheaper than reading the whole frame.
    """
    work = to_working_size(bgr)
    cells = cell_scores(work)
    mask = cells >= CELL_IS_SCREEN
    h, w = work.shape[:2]
    rows, cols = GRID
    found = []
    for n, r0, r1, c0, c1 in clusters(mask):
        if n < min_cells:
            continue
        y0, y1 = r0 * h // rows, (r1 + 1) * h // rows
        x0, x1 = c0 * w // cols, (c1 + 1) * w // cols
        crop = work[max(0, y0 - 8):min(h, y1 + 8), max(0, x0 - 8):min(w, x1 + 8)]
        if crop.size == 0 or min(crop.shape[:2]) < 24:
            continue
        scale = max(1, int(900 / max(1, crop.shape[1])))
        if scale > 1:
            crop = cv2.resize(crop, (crop.shape[1] * scale, crop.shape[0] * scale),
                              interpolation=cv2.INTER_LANCZOS4)
        res, _ = engine(crop)
        boxes = len(res) if res else 0
        if boxes >= min_boxes and rows_aligned(res):
            found.append({"cells": n, "boxes": boxes,
                          "box": (x0, y0, x1, y1),
                          "share": n / (rows * cols)})
    return found


if __name__ == "__main__":
    import sys, glob, os
    paths = []
    for a in sys.argv[1:]:
        paths.extend(sorted(glob.glob(a)))
    from rapidocr_onnxruntime import RapidOCR
    eng = RapidOCR()
    for p in paths:
        bgr = cv2.imread(p)
        regions = ui_regions(bgr, eng)
        _, frac, s = verdict(bgr)
        if regions:
            biggest = regions[0]
            where = biggest["box"]
            print(f"{os.path.basename(p):>18}  UI      "
                  f"{sum(r['share'] for r in regions)*100:5.1f}% of frame, "
                  f"{len(regions)} region(s), largest at x{where[0]}-{where[2]} "
                  f"y{where[1]}-{where[3]} with {biggest['boxes']} text items")
        else:
            print(f"{os.path.basename(p):>18}  no UI   "
                  f"(flat area {frac*100:.0f}%, no text in it)")
