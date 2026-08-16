#!/usr/bin/env python3
"""Read the panels a live stream draws over its picture.

    python3 overlay.py <frame.png>

A live stream is mostly a camera, with interface laid on top of it: a donation
counter, an alert that somebody followed, a lower third. The rest of this
build reads interface that fills a window; here the interface is a few small
rectangles floating on a photograph, and the first question is not what they
say but WHICH of the text on screen is interface at all.

That question is harder than it sounds. Seven ways of answering it were
measured on frames holding both kinds -- a "jaredrhod.com" banner the
application drew, and a "FALSE" sticker on the shelf behind Jared -- and the
first seven all failed, several of them backwards, because the sticker is
printed matter photographed close up and comes out crisper and purer than a
banner drawn over moving video:

  exact-pixel ties, the measure that separates a screen recording from a
  camera elsewhere in this build, put the banner BELOW the sticker (0.24
  against 0.44). Over moving video a banner's own soft edges break ties.

  motion between frames a second apart put the sticker (25) below the chat
  (159 and up), because the chat scrolls. Drawn is not the same as still.

  flat colour found nothing, because a dim room is flat everywhere: the
  frame's median local deviation was 0.6 grey levels.

  the exact painted colour found the panel on one frame and not the other,
  because the room is lit green and shares the panel's own green.

  the purity of the ink put the sticker first on both frames (28 against 44).

  the sharpness of the glyph edges did the same (0.25 against 0.60).

  the evenness of the stroke did not order them at all.

Two things do work, and this module is the two of them.

A PANEL is found by its edges. An application draws a rectangle: two
horizontal steps and two vertical, each running dead straight for hundreds of
pixels at exactly one x or one y, which nothing photographed holds. Two card
edges with video between them make a rectangle just as square, and the fill
separates those -- a drawn fill is one value.

TEXT with no panel round it is judged not by how it looks but by how it
behaves against the ground it sits on, over minutes rather than seconds. An
overlay is composited on top: the picture behind it changes and it does not. A
sticker is part of that picture and changes with it. See standing_text.
"""
import os
import sys

import cv2
import numpy as np

import note_reader
import machine

RUN = 0.04            # an edge runs this far across the frame to count
MIN_SIDE = 40         # and a panel is at least this many pixels each way
MAX_SHARE = 0.55      # a rectangle covering more than this is the picture
OVERLAP = 0.6         # two edges bound one panel if they line up this well
GAP_TO_HEIGHT = 1.2   # a gap wider than the text is tall splits label from value
FILL_SPREAD = 2.0     # a drawn fill is one value; two levels allows for the codec
SPAN = 600            # seconds the frames judging steadiness are spread over
LOOKS = 4             # and how many of them
WINDOW_RUN = 0.08     # a window side runs this far across the frame
WINDOW_SIDE = 80      # and a window is at least this many pixels each way
CORNER = 0.15         # its sides may start this far in, for rounded corners


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
    """EVERY unbroken run of edge on each line that is long enough.

    Every one of them, not the longest: a drawn edge can be crossed by
    something and arrive in pieces. The donation card's lower edge is broken
    by the glare of the lamp behind Jared, and on one grab of that second the
    surviving piece of its lower edge and the surviving piece of its upper
    edge did not overlap, so the rectangle they bound was never proposed and
    the card was not found at all -- on a frame where it is unmistakable to
    the eye. On another grab of the SAME second the pieces happened to
    overlap and it was found. An instrument that depends on which grab it got
    is not an instrument.
    """
    out = []
    count = strong.shape[axis]
    for i in range(count):
        line = strong[i, :] if axis == 0 else strong[:, i]
        at = None
        for j, on in enumerate(line):
            if on and at is None:
                at = j
            elif not on and at is not None:
                if j - at >= need:
                    out.append((i, at, j))
                at = None
        if at is not None and len(line) - at >= need:
            out.append((i, at, len(line)))
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


def read_panel(bgr, box, scratch, engine=None):
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
    # this reader's engine is tesseract, so the OTHER one checks it: a panel
    # whose lettering neither engine agrees on is a picture of text, and the
    # browser toolbar it kept finding is exactly that
    import verify_names
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    res, _ = engine(path)
    said = " ".join(t for _, t, _ in (res or []))
    unsettled = [t for t, ok in verify_names.confirm_readings(path, lines, said)
                 if not ok]
    if left and right:
        return {"lines": lines, "label": " ".join(left),
                "value": " ".join(right), "unsettled": unsettled}
    return {"lines": lines, "label": None, "value": None,
            "unsettled": unsettled}


def read_overlays(png_path, engine=None):
    bgr = cv2.imread(png_path)
    if bgr is None:
        return {"panels": [], "why": "could not read the image"}
    out = []
    for n, box in enumerate(panels(bgr)):
        got = read_panel(
            bgr, box, png_path.replace(".png", f"_panel{n}.png"), engine)
        if not got["lines"]:
            continue
        got["box"] = box
        out.append(got)
    return {"panels": out}


def windows(bgr, run=WINDOW_RUN, min_side=WINDOW_SIDE):
    """The application windows on a desktop, by their four drawn sides.

    A frame is not always one window. Jared works across a whole desktop --
    a full-screen HUD on the left, the Clock app in the middle, a browser on
    the right -- and split into vertical strips, as a single window is, the
    three run together: the menu bar came back as a folder tree with "Clock"
    and "File Edit" for folders, and everything else landed in one strip that
    was read as loose text.

    A window is the same rectangle a panel is, minus the one thing a panel
    has: its interior is not a single colour, because a window has contents.
    So the interior is not asked about at all, and instead ALL FOUR sides must
    be drawn -- two horizontal edges, and a vertical edge standing at each end
    of them through the whole height between. A panel found this way is a real
    box either way; what is refused is a rectangle inferred from two sides and
    a hope, which is how a stretch of empty desktop becomes a window.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    across = merge_runs(runs_along(strong_steps(gray, 0), 0, int(w * run)))
    down = merge_runs(runs_along(strong_steps(gray, 1), 1, int(h * run)))
    found = []
    for a in range(len(across)):
        ya, a0, a1 = across[a]
        for b in range(a + 1, len(across)):
            yb, b0, b1 = across[b]
            if yb - ya < min_side:
                continue
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo < min_side:
                continue
            # a window's corners are rounded, so its sides start a little
            # inside its top and stop a little short of its bottom -- the
            # Clock app's left edge begins one pixel below where a fixed
            # allowance would have accepted it. The allowance is a share of
            # the window's own height instead, which does not care how big
            # the window is.
            room = (yb - ya) * CORNER
            sides = [d for d in down if d[1] <= ya + room and d[2] >= yb - room]
            left = [d[0] for d in sides if abs(d[0] - lo) < min_side]
            right = [d[0] for d in sides if abs(d[0] - hi) < min_side]
            if not left or not right:
                continue
            found.append(((hi - lo) * (yb - ya),
                          (min(left), ya, max(right) + 1, yb)))
    found.sort(reverse=True)
    kept = []
    for _, box in found:
        x0, y0, x1, y1 = box
        mine = (x1 - x0) * (y1 - y0)
        clash = False
        for X0, Y0, X1, Y1 in kept:
            over = (max(0, min(x1, X1) - max(x0, X0))
                    * max(0, min(y1, Y1) - max(y0, Y0)))
            # windows sit side by side and their borders touch, so ANY overlap
            # is the wrong test -- one shared pixel column had the browser
            # thrown away as a duplicate of the Clock beside it
            if over * 2 > min(mine, (X1 - X0) * (Y1 - Y0)):
                clash = True
                break
        if not clash:
            kept.append(box)
    kept.sort(key=lambda b: (b[0], b[1]))
    return kept


def frames_across(video, at, span=SPAN, looks=LOOKS, workdir=None):
    """A handful of frames spread across a window, for judging what stands still.

    The window is minutes wide on purpose. Over a second or two a camera in a
    dim room barely changes and neither does an overlay, so nothing separates;
    over ten minutes the room has been lit differently, sat in differently and
    walked in front of, and an overlay has not moved a pixel.
    """
    import subprocess
    import tempfile
    workdir = workdir or tempfile.mkdtemp(prefix="standing_")
    os.makedirs(workdir, exist_ok=True)
    out = []
    for i in range(looks):
        t = max(0.0, at - span / 2 + span * i / max(1, looks - 1))
        path = os.path.join(workdir, f"look_{i:02d}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
                        "-frames:v", "1", "-y", path], capture_output=True)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            out.append(path)
    return out


def standing_text(paths, engine=None):
    """The text on the picture that is PROVEN to have been drawn on it.

    A banner reading "jaredrhod.com" and a sticker reading "FALSE" on the shelf
    behind Jared are both text to a recogniser, and seven measurements failed
    to tell them apart: exact-pixel ties, motion over a second, flat colour,
    the exact painted colour, the purity of the ink, the sharpness of the
    glyph edges and the evenness of the stroke. Several put them the wrong way
    round -- the sticker is printed matter photographed close up, so it is
    crisper and purer than a banner drawn over moving video.

    What separates them is not how the text looks but how it behaves against
    the ground it sits on. An overlay is composited on top: the picture behind
    it changes and IT does not. A sticker is part of that picture and changes
    with it -- lit by the same lamps, moved by the same camera, walked in
    front of by the same person. So the test is a comparison, not a threshold:

        drawn, if the glyphs changed no more than the ground around them,
        and the glyphs are stiller than HALF THE FRAME is
        -- and only where the ground changed at all, since nothing is proved
        by standing still in front of something that also stood still

    The second line is the one that costs to leave out, and it was left out.
    Comparing the glyphs only against their own ground says nothing about how
    much either moved: on a third video a sticker changed 161 against a ground
    of 178 and passed, along with six other fragments of the room -- BEST,
    CALTY, BITCH, PEOPLE, XING -- every one of them moving five to nine times
    as much as the stillest quarter of that frame. Drawn text does not move.
    Requiring it to be stiller than the frame's own median says that without
    naming a number, because the frame supplies the number.

    Measured over ten minutes on three videos. The banner's glyphs changed 21
    against a ground of 33 and a frame median of 37, and 13 against 35 and 40.
    The sticker's changed 48 against 51 with a median of 40, and 161 against
    178 with a median of 52. The banner is the only text admitted on either
    stream, and on the third video nothing is admitted at all.

    Nothing is claimed about text this cannot prove. A chat line scrolls away
    and a counter ticks over, so both fail the test though both are drawn;
    they have their own readers, and a verdict of "no evidence" costs nothing
    where an "in the room" would have been wrong.

    ASK THIS ONLY WHERE THERE IS A PICTURE. The question is whether the text
    was composited over the camera, and on a frame that is mostly interface it
    has no meaning: everything on a screen recording is drawn. Left ungated it
    admitted "SOM", a fragment of a poster, from a frame that was 100%
    interface. The two frames carrying the banner are 25% and 10% interface;
    the two where the room crept in are 67% and 100%. The caller holds that
    share, so the caller holds the gate -- see pipeline.py.
    """
    if len(paths) < 3:
        return []
    shots = [cv2.imread(p) for p in paths]
    shots = [s for s in shots if s is not None]
    if len(shots) < 3 or len({s.shape for s in shots}) != 1:
        return []
    stack = np.stack([s.astype(np.int16) for s in shots])
    change = np.abs(stack - stack[0]).max(axis=0).max(axis=2)
    still = float(np.percentile(change, 25))
    # how much this frame moves altogether, which is what "stiller than the
    # picture it sits on" has to be measured against
    moving = float(np.median(change))
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    res, _ = engine(paths[0])
    out = []
    for box, text, _conf in (res or []):
        x0 = int(min(q[0] for q in box)); x1 = int(max(q[0] for q in box))
        y0 = int(min(q[1] for q in box)); y1 = int(max(q[1] for q in box))
        if x1 - x0 < 14 or y1 - y0 < 8:
            continue
        gray = cv2.cvtColor(shots[0][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        ink = note_reader.ink_mask(gray)
        if ink.sum() < 25 or (~ink).sum() < 25:
            continue
        here = change[y0:y1, x0:x1]
        glyphs = float(np.median(here[ink]))
        ground = float(np.median(here[~ink]))
        if ground <= still or glyphs > ground or glyphs > moving:
            continue
        out.append({"text": text.strip(), "box": (x0, y0, x1, y1),
                    "glyphs": glyphs, "ground": ground})
    return out


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
