#!/usr/bin/env python3
"""Read the panels a live stream draws over its picture.

    python3 overlay.py <frame.png>

A live stream is mostly a camera, with interface laid on top of it: a donation
counter, an alert that somebody followed, a lower third. The rest of this
build reads interface that fills a window; here the interface is a few small
rectangles floating on a photograph, and the first question is not what they
say but WHICH of the text on screen is interface at all.

That question is harder than it sounds, and four ways of answering it were
measured on one frame that holds both kinds -- a "jaredrhod.com" banner the
application drew, and a "FALSE" sticker on the shelf behind Jared:

  exact-pixel ties, the measure that separates a screen recording from a
  camera elsewhere in this build, put the banner BELOW the sticker (0.24
  against 0.44). Over moving video the banner's own soft edges break ties.

  motion between frames a second apart put the sticker (25) below the chat
  (159 and up), because the chat scrolls. Drawn is not the same as still.

  flat colour found nothing, because a dim room is flat everywhere: the
  frame's median local deviation was 0.6 grey levels.

  the exact painted colour found the panel on one frame and not the other,
  because the room is lit green and shares the panel's own green.

What does work is the one thing an application does and a room cannot: it
draws a RECTANGLE. Two horizontal steps and two vertical ones, each running
dead straight for hundreds of pixels at exactly one x or one y. Nothing
photographed holds a line like that. So the panels are found by their edges,
and only text inside a panel is called interface.

Text floating on the picture with no panel round it -- the "jaredrhod.com"
banner -- is left alone deliberately. Nothing measured here tells it from a
sticker on the shelf, and calling a sticker interface is the invention this
build exists to prevent.
"""
import sys

import cv2
import numpy as np

import note_reader

RUN = 0.04            # an edge runs this far across the frame to count
MIN_SIDE = 40         # and a panel is at least this many pixels each way
MAX_SHARE = 0.55      # a rectangle covering more than this is the picture
OVERLAP = 0.6         # two edges bound one panel if they line up this well
GAP_TO_HEIGHT = 1.2   # a gap wider than the text is tall splits label from value
FILL_SPREAD = 2.0     # a drawn fill is one value; two levels allows for the codec


def strong_steps(gray, axis):
    """Where the picture steps sharply, across or down.

    The size of a step that counts is taken from the frame itself: an edge
    stands against the noise of the picture it is drawn on, and a dim room and
    a bright slide do not have the same noise.
    """
    step = np.abs(np.diff(gray.astype(np.int16), axis=axis))
    lim = float(np.percentile(step, 99.0))
    return step > max(8.0, lim * 0.5)


def runs_along(strong, axis, need):
    """The longest unbroken run of edge on each line, where it is long enough."""
    out = []
    count = strong.shape[axis]
    for i in range(count):
        line = strong[i, :] if axis == 0 else strong[:, i]
        best = start = run = 0
        at = None
        for j, on in enumerate(line):
            if on:
                if at is None:
                    at = j
                run += 1
                if run > best:
                    best, start = run, at
            else:
                run, at = 0, None
        if best >= need:
            out.append((i, start, start + best))
    return out


def merge_runs(runs, near=3):
    """One drawn edge, not the three rows of pixels it lands on.

    A border a couple of pixels thick answers on each of them, and the outer
    rows answer for a shorter stretch than the middle one. Left separate, the
    short outer row makes a rectangle a shade smaller than the real one and
    wins, because it is a shade smaller. So the rows of one edge are grouped
    and the longest stands for all of them.
    """
    out = []
    for i, a, b in runs:
        if out and i - out[-1][0] <= near and min(b, out[-1][2]) - max(a, out[-1][1]) > 0:
            if b - a > out[-1][2] - out[-1][1]:
                out[-1] = (out[-1][0], a, b)
            continue
        out.append((i, a, b))
    return out


def painted(bgr, box):
    """Is this rectangle a drawn fill, or a piece of the picture?

    An application paints a panel in ONE value. Two card edges with video
    between them make a rectangle just as square as a card does, and this is
    what tells them apart: the card's interior varies by nothing at all, the
    video's by several levels. Measured on one frame carrying both, the three
    cards came to 0, 0 and 1, and the strip of video between two of them to 5.
    """
    x0, y0, x1, y1 = box
    inside = bgr[y0:y1, x0:x1].reshape(-1, 3)
    if inside.size == 0:
        return False
    spread = np.median(np.abs(inside - np.median(inside, axis=0)))
    return float(spread) <= FILL_SPREAD


def widen(bgr, box):
    """Grow a panel sideways while its own colour continues.

    An edge is only found where the panel stands against something that
    contrasts with it. The donation card's right half sits over a dark desk
    and shows its edge; its left half sits over darker desk still and does
    not. The colour inside the panel does not care: it runs the whole width.
    """
    x0, y0, x1, y1 = box
    band = bgr[y0:y1, x0:x1]
    if band.size == 0:
        return box
    inside = np.median(band.reshape(-1, 3), axis=0)
    spread = float(np.median(np.abs(band.reshape(-1, 3) - inside)))
    room = max(6.0, spread * 2)
    for side in (-1, 1):
        x = x0 if side < 0 else x1
        while 0 < x < bgr.shape[1] - 1:
            col = bgr[y0:y1, x - 1 if side < 0 else x]
            if float(np.median(np.abs(np.median(col, axis=0) - inside))) > room:
                break
            x += side
        if side < 0:
            x0 = x
        else:
            x1 = x
    return (x0, y0, x1, y1)


def panels(bgr):
    """Every rectangle the picture has drawn on it."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    across = merge_runs(runs_along(strong_steps(gray, 0), 0, int(w * RUN)))
    down = merge_runs(runs_along(strong_steps(gray, 1), 1, int(h * RUN)))
    if not across:
        return []
    pairs = []
    for a in range(len(across)):
        ya, a0, a1 = across[a]
        for b in range(a + 1, len(across)):
            yb, b0, b1 = across[b]
            if yb - ya < MIN_SIDE:
                continue
            if (yb - ya) * (b1 - b0) > MAX_SHARE * w * h:
                continue
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo < MIN_SIDE:
                continue
            if (hi - lo) < OVERLAP * min(a1 - a0, b1 - b0):
                continue
            pairs.append((yb - ya, lo, ya, hi, yb))
    pairs.sort()
    taken, out = [], []
    for _, x0, y0, x1, y1 in pairs:
        # the tightest rectangle wins the rows it covers, so a card is not
        # reported again as part of the stack of cards above and below it
        if any(not (y1 <= t0 or y0 >= t1) for t0, t1 in taken):
            continue
        taken.append((y0, y1))
        left = [d for d in down if d[1] <= y0 + 2 and d[2] >= y1 - 2]
        near = [d[0] for d in left if abs(d[0] - x0) < MIN_SIDE]
        far = [d[0] for d in left if abs(d[0] - x1) < MIN_SIDE]
        box = (min(near) if near else x0, y0,
               max(far) + 1 if far else x1, y1)
        box = widen(bgr, box)
        if painted(bgr, box):
            out.append(box)
    out.sort(key=lambda b: (b[1], b[0]))
    return out


def read_panel(bgr, box, scratch):
    """What one panel says, and how it is laid out.

    A counter puts its name on the left and its number on the right, wrapped
    over as many lines as it needs; an alert puts a title over a sentence.
    Both come back as rows, and the rows are split into two sides only where
    every one of them has a gap wide enough to be a column rather than a
    space.
    """
    x0, y0, x1, y1 = box
    crop = bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return {"lines": [], "label": None, "value": None}
    big = cv2.resize(crop, (crop.shape[1] * 3, crop.shape[0] * 3),
                     interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(scratch, big)
    path = scratch
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    rows = [r for r in note_reader.tess_rows(path, gray) if r["text"].strip()]
    rows.sort(key=lambda r: r["y0"])
    lines = [r["text"].strip() for r in rows]
    left, right = [], []
    for r in rows:
        words = r.get("words") or []
        if len(words) < 2:
            left, right = [], []
            break
        tall = r["y1"] - r["y0"]
        gaps = [(words[i + 1][1] - words[i][2], i) for i in range(len(words) - 1)]
        widest, where = max(gaps)
        if widest < tall * GAP_TO_HEIGHT:
            left, right = [], []
            break
        left.append(" ".join(w[0] for w in words[:where + 1]))
        right.append(" ".join(w[0] for w in words[where + 1:]))
    if left and right:
        return {"lines": lines, "label": " ".join(left),
                "value": " ".join(right)}
    return {"lines": lines, "label": None, "value": None}


def read_overlays(png_path):
    bgr = cv2.imread(png_path)
    if bgr is None:
        return {"panels": [], "why": "could not read the image"}
    out = []
    for n, box in enumerate(panels(bgr)):
        got = read_panel(
            bgr, box, png_path.replace(".png", f"_panel{n}.png"))
        if not got["lines"]:
            continue
        got["box"] = box
        out.append(got)
    return {"panels": out}


def render(res):
    if not res.get("panels"):
        return "NO DRAWN PANELS - " + res.get("why", "nothing rectangular on "
                                                     "the picture")
    out = []
    for p in res["panels"]:
        x0, y0, x1, y1 = p["box"]
        out.append(f"[panel at {x0},{y0} {x1 - x0}x{y1 - y0}]")
        if p["label"]:
            out.append(f"  {p['label']}: {p['value']}")
        else:
            for line in p["lines"]:
                out.append(f"  {line}")
    return "\n".join(out)


if __name__ == "__main__":
    print(render(read_overlays(sys.argv[1])))
