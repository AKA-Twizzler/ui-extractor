"""style_reader.py -- what a pane looks like, beyond the words on it.

Every measurement here answers one question a drawn window needs answered
that the text readers do not ask:

    look(bgr)                 dark or light, and the background colour
    bands(bgr)                rows drawn on a coloured band: a selection,
                              a highlight, a header strip
    icons_before(bgr, rows)   a small drawn mark to the left of a row's text
    pictures(bgr, boxes)      regions with no text on them but plenty of
                              picture: an image, a thumbnail, a chart
    slant(mask)               the lean of a row's strokes -- italic
    italic_words(mask, words, xh)  the words of a row that lean
    underline(mask, xh)       a rule drawn under a row's words
    pitch(mask, xh)           monospace or proportional, by glyph advance
    pointer(gray)             the mouse pointer, by its arrow shape

Each is measured on the pixels and returns numbers beside its verdict, so
the record carries what was seen and the verdict can be re-judged later.
Nothing here reads text; nothing here guesses from a name.
"""
import cv2
import numpy as np

BAND_DIFF = 40        # a band's colour differs from the background by this much, summed over BGR
BAND_MIN_H = 4        # and is at least this tall, so a hairline rule is not a band
INK_MARGIN = 40
ITALIC_DEG = 7.0      # strokes leaning past this are italic
UNDERLINE_FILL = 0.6  # one unbroken run covers this much of the words' width
MONO_SHARE = 0.7      # this share of advances on one pitch is monospace

_HUES = ((10, "red"), (22, "orange"), (33, "yellow"), (78, "green"),
         (100, "cyan"), (128, "blue"), (155, "purple"), (175, "pink"),
         (181, "red"))


def hue_name(bgr_triplet, sat_floor=45):
    dom = np.array(bgr_triplet, dtype=np.uint8).reshape(1, 1, 3)
    h, s, v = cv2.cvtColor(dom, cv2.COLOR_BGR2HSV)[0, 0]
    if int(s) < sat_floor:
        return "grey" if 40 < int(v) < 215 else ("white" if int(v) >= 215 else "black")
    for top, name in _HUES:
        if int(h) <= top:
            return name
    return "red"


def ink_mask(gray):
    bg = cv2.medianBlur(gray, 21)
    lighter = cv2.subtract(gray, bg)
    darker = cv2.subtract(bg, gray)
    return cv2.max(lighter, darker) > INK_MARGIN


# ------------------------------------------------------------------ look

def look(bgr):
    """Dark or light, from the background the pane is painted on."""
    bg = np.median(bgr.reshape(-1, 3), axis=0)
    lum = float(0.114 * bg[0] + 0.587 * bg[1] + 0.299 * bg[2])
    return {"theme": "dark" if lum < 128 else "light",
            "background": [int(v) for v in bg], "luminance": round(lum, 1)}


# ----------------------------------------------------------------- bands

def bands(bgr):
    """Horizontal bands painted a different colour from the background.

    A selected row, a highlighted line, a header strip: each is a run of
    scan lines whose MEDIAN colour -- the paint, not the ink on it -- is not
    the background's. Measured on the Finder at 00:03:00 of the memory-files
    video: background (31,31,32); the Dev row a 68 px band at (45,137,68),
    green; the header strip and the path bar, greys a shade lighter.
    """
    bg = np.median(bgr.reshape(-1, 3), axis=0)
    per_y = np.median(bgr, axis=1)
    diff = np.abs(per_y - bg).sum(axis=1)
    ys = np.where(diff > BAND_DIFF)[0]
    out = []
    for y in ys:
        if out and y - out[-1]["y1"] <= 2:
            out[-1]["y1"] = int(y)
        else:
            out.append({"y0": int(y), "y1": int(y)})
    kept = []
    for b in out:
        if b["y1"] - b["y0"] + 1 < BAND_MIN_H:
            continue
        colour = per_y[b["y0"]:b["y1"] + 1].mean(axis=0)
        b["colour"] = [int(v) for v in colour]
        b["hue"] = hue_name(colour)
        b["height"] = b["y1"] - b["y0"] + 1
        kept.append(b)
    return kept


def band_of(bands_, y0, y1):
    """The band a row sits on, if most of the row's height is inside one."""
    for b in bands_:
        top, bottom = max(b["y0"], y0), min(b["y1"], y1)
        if bottom - top >= 0.6 * max(1, y1 - y0):
            return b
    return None


# ----------------------------------------------------------------- icons

def icons_before(bgr, rows, reach=2.2):
    """A drawn mark just left of each row's text: a folder, a file, a dot.

    The strip from the text's left edge back by about two row heights is
    asked for ink that is not the background. An icon is a compact blob
    there; a chevron or bullet is one too, and the caller says which by the
    reader that found the row. Returns one entry per row: None, or the
    mark's box and dominant colour.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = ink_mask(gray)
    H, W = gray.shape
    out = []
    for r in rows:
        x0, y0, x1, y1 = int(r["x0"]), int(r["y0"]), int(r["x1"]), int(r["y1"])
        h = max(4, y1 - y0)
        a = max(0, int(x0 - reach * h))
        b = max(a, x0 - 2)
        if b - a < 4:
            out.append(None)
            continue
        cell = mask[max(0, y0 - 2):min(H, y1 + 2), a:b]
        if cell.size == 0 or int(cell.sum()) < max(12, 0.04 * cell.size):
            out.append(None)
            continue
        ys, xs = np.where(cell)
        bx0, bx1 = a + int(xs.min()), a + int(xs.max()) + 1
        by0, by1 = max(0, y0 - 2) + int(ys.min()), max(0, y0 - 2) + int(ys.max()) + 1
        crop = bgr[by0:by1, bx0:bx1]
        inkpx = crop[mask[by0:by1, bx0:bx1]] if crop.size else np.zeros((0, 3))
        colour = np.median(inkpx.reshape(-1, 3), axis=0) if len(inkpx) else np.array([0, 0, 0])
        # a coloured mark beside a grey chevron: the colour is the mark's,
        # so the saturated pixels name it when there are enough of them
        if len(inkpx):
            hsv = cv2.cvtColor(inkpx.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV)[:, 0, :]
            sat = inkpx[hsv[:, 1] > 60]
            if len(sat) >= 20 and len(sat) >= 0.25 * len(inkpx):
                colour = np.median(sat.reshape(-1, 3), axis=0)
        out.append({"box": [bx0, by0, bx1, by1], "fill": round(float(cell.mean()), 3),
                    "colour": [int(v) for v in colour], "hue": hue_name(colour)})
    return out


# -------------------------------------------------------------- pictures

def pictures(bgr, text_boxes, cell=48, min_cells=4):
    """Regions that hold a picture: busy pixels where no text was read.

    The pane is cut into cells; a cell is busy when its pixels vary well
    beyond flat paint and it does not touch a text reading. Busy cells that
    touch are one picture. A thumbnail, a chart, the webcam inset, a logo:
    each comes back as a box with its size and how busy it is, so the note
    can draw a placeholder where it sat rather than nothing.
    """
    H, W = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    ny, nx = max(1, H // cell), max(1, W // cell)
    busy = np.zeros((ny, nx), bool)
    score = np.zeros((ny, nx), float)
    covered = np.zeros((H, W), bool)
    for x0, y0, x1, y1 in text_boxes:
        covered[max(0, y0 - 4):min(H, y1 + 4), max(0, x0 - 4):min(W, x1 + 4)] = True
    # a painted band's edges are not a picture
    for b in bands(bgr):
        covered[max(0, b["y0"] - 2):min(H, b["y1"] + 3), :] = True
    for j in range(ny):
        for i in range(nx):
            ys, xs = slice(j * cell, (j + 1) * cell), slice(i * cell, (i + 1) * cell)
            if covered[ys, xs].mean() > 0.15:
                continue
            patch = gray[ys, xs]
            sd = float(patch.std())
            # a picture has many grey levels; text on paint has two
            levels = len(np.unique(patch // 16))
            if sd > 18 and levels >= 6:
                busy[j, i] = True
                score[j, i] = sd
    n, labels = cv2.connectedComponents(busy.astype(np.uint8), connectivity=4)
    out = []
    for k in range(1, n):
        cells_ = np.argwhere(labels == k)
        if len(cells_) < min_cells:
            continue
        j0, i0 = cells_.min(axis=0)
        j1, i1 = cells_.max(axis=0)
        box = [int(i0 * cell), int(j0 * cell), int(min(W, (i1 + 1) * cell)), int(min(H, (j1 + 1) * cell))]
        crop = bgr[box[1]:box[3], box[0]:box[2]]
        colour = np.median(crop.reshape(-1, 3), axis=0)
        out.append({"box": box, "cells": int(len(cells_)),
                    "busy": round(float(score[labels == k].mean()), 1),
                    "colour": [int(v) for v in colour], "hue": hue_name(colour)})
    out.sort(key=lambda p: -p["cells"])
    return out


# ----------------------------------------------------------------- slant

def slant(mask):
    """The lean of a row's strokes, in degrees; positive leans right.

    The row's ink is sheared through a range of angles and the one that
    makes its column profile sharpest -- vertical strokes stacked on the
    fewest columns -- is the lean the strokes were drawn at. Upright text
    peaks near zero; italic near ten to fifteen degrees.
    """
    h, w = mask.shape
    if h < 6 or w < 6 or int(mask.sum()) < 30:
        return 0.0
    src = mask.astype(np.uint8) * 255
    best, best_score = 0.0, -1.0
    for deg in np.arange(-20, 21, 1.0):
        t = np.tan(np.radians(deg))
        M = np.float32([[1, -t, t * h / 2], [0, 1, 0]])
        sheared = cv2.warpAffine(src, M, (w + int(abs(t) * h) + 2, h), flags=cv2.INTER_NEAREST)
        prof = (sheared > 0).sum(axis=0).astype(float)
        score = float((prof ** 2).sum())
        if score > best_score:
            best_score, best = score, float(deg)
    # the shear that straightens a right-leaning stroke is a negative
    # angle here; the answer is given the way a person reads it, so
    # italic -- leaning right -- is positive
    return -best


def italic_words(mask, words, xh, floor=ITALIC_DEG):
    """Which of a row's words lean: each word measured on its own.

    A row's lean is the lean of most of its words, so one italic phrase in
    a line of upright prose is invisible at row level -- measured: "Every
    agent w", the only italic on a note page, read 9 degrees as a word and
    the row it sat on read 0. Words with a slash or a bracket in them are
    not asked: a diagonal stroke leans the whole measurement, and "Notes/"
    read 20 degrees upright.
    """
    out = []
    for w in words or []:
        text, x0, x1 = w[0], int(w[1]), int(w[2])
        core = text.strip(".,;:!?'\"")
        if len(core) < 4 or not core.replace("'", "").isalnum():
            continue
        cell = mask[:, max(0, x0):x1]
        if cell.size == 0:
            continue
        deg = slant(cell)
        if deg >= floor:
            out.append({"word": text, "slant": deg, "x0": x0, "x1": x1})
    return out


# ------------------------------------------------------------- underline

def underline(mask, xh):
    """A rule under the words: one unbroken horizontal run below the letters.

    Fill alone cannot tell a rule from a baseline -- the bottoms of the
    letters on a line of prose fill 0.55 of its width, measured on every
    row of a note -- but they never touch: the gaps between letters and
    words break the run. A rule is one run, unbroken, across most of the
    words' width, one to three pixels tall, in the lower part of the row.
    """
    h, w = mask.shape
    if h < 6 or w < 10:
        return None
    cols = np.where(mask.any(axis=0))[0]
    if len(cols) == 0:
        return None
    span = cols.max() - cols.min() + 1
    lo = int(h * 0.55)
    found = None
    for y in range(h - 1, lo, -1):
        row = mask[y]
        # the longest unbroken run on this scan line
        best, run = 0, 0
        for v in row:
            run = run + 1 if v else 0
            best = max(best, run)
        if best >= UNDERLINE_FILL * span:
            if found is None:
                found = {"y": y, "thickness": 1, "run": best}
            else:
                found["y"] = y
                found["thickness"] += 1
        elif found is not None:
            break
    if found is None or found["thickness"] > max(3, xh * 0.25):
        return None
    found["fill"] = round(found["run"] / span, 2)
    return found


# ----------------------------------------------------------------- pitch

def pitch(mask, xh):
    """Monospace or proportional, from how the glyphs advance.

    Letters are found as connected ink; the distances between successive
    left edges are the advances. Monospace puts every advance on one pitch
    or a whole multiple of it (the spaces); proportional text scatters them.
    """
    h, w = mask.shape
    if int(mask.sum()) < 40:
        return None
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    lefts = sorted(int(stats[k, cv2.CC_STAT_LEFT]) for k in range(1, n)
                   if stats[k, cv2.CC_STAT_HEIGHT] >= 0.4 * max(1, xh))
    if len(lefts) < 8:
        return None
    adv = np.diff(lefts)
    adv = adv[adv > 1]
    if len(adv) < 6:
        return None
    base = float(np.median(adv))
    if base <= 0:
        return None
    on = 0
    for a in adv:
        k = max(1, round(a / base))
        if abs(a - k * base) <= 0.15 * base:
            on += 1
    share = on / len(adv)
    return {"pitch": round(base, 1), "on_pitch": round(share, 2),
            "family": "monospace" if share >= MONO_SHARE else "proportional"}


# --------------------------------------------------------------- pointer

POINTER_FLOOR = 0.7     # a normalised match this strong is the pointer; frames
                        # with none measured 0.55 at best
_POINTER = None


def _template():
    global _POINTER
    if _POINTER is None:
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pointer.png")
        _POINTER = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    return _POINTER


def pointer(gray, floor=POINTER_FLOOR):
    """Where the mouse pointer is, by matching the real pointer's pixels.

    The template is the pointer itself, cut from a 4K frame of the
    memory-files video at 00:03:00: a black arrow with a white rim, 29 by
    50 pixels at 2160 lines. A drawn polygon was tried first and never
    matched above 0.6; the real pixels match at 1.0 on their own frame and
    0.875 on another where the pointer stood at half the size. A frame
    with no pointer on it tops out near 0.55, so the floor sits at 0.7.
    The size is not assumed: a ladder of scales, set by the frame's height,
    finds the pointer at whatever size the screen was captured at.
    """
    t = _template()
    if t is None:
        return None
    unit = gray.shape[0] / 2160.0
    best = None
    for sc in (0.35, 0.5, 0.75, 1.0, 1.25):
        f = sc * unit
        if f <= 0:
            continue
        tt = cv2.resize(t, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        if tt.shape[0] < 8 or gray.shape[0] < tt.shape[0] * 2 or gray.shape[1] < tt.shape[1] * 2:
            continue
        res = cv2.matchTemplate(gray, tt, cv2.TM_CCOEFF_NORMED)
        _, val, _, loc = cv2.minMaxLoc(res)
        if val >= floor and (best is None or val > best["score"]):
            best = {"box": [int(loc[0]), int(loc[1]),
                            int(loc[0] + tt.shape[1]), int(loc[1] + tt.shape[0])],
                    "scale": round(sc, 2), "score": round(float(val), 3)}
    return best
