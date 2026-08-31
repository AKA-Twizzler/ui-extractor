"""How far a moment is zoomed in, MEASURED against a reference frame.

WHY THIS EXISTS. The drawing works the zoom out by matching where OCR'd WORDS
sat between two frames -- `words_of = {m["ts"]: word_boxes(m) for m in moments}`
in draw3 -- which is geometry inferred from text, a guess built on a guess. It
is why the pictures have not moved in five builds: every one of them is drawn at
a scale nobody measured.

WHAT THIS DOES INSTEAD. A zoomed moment is a CROP of the same desktop, enlarged.
So the moment's frame, shrunk by the right amount, appears inside the reference
frame exactly. Shrink it by a ladder of amounts, look for it in the reference
each time, and the amount that matches best IS the zoom. That is arithmetic on
light and dark: no words, no reading, no engine.

It reports its own confidence and returns None below a floor, because a wrong
scale drawn confidently is worse than no scale at all.
"""

import numpy as np

WORK = 480          # the reference is worked at this width; the ladder scales from it
FLOOR = 0.45        # a match below this is not a match
LADDER = [1.00, 0.90, 0.80, 0.70, 0.62, 0.55, 0.48, 0.42, 0.36, 0.31,
          0.27, 0.23, 0.20, 0.17, 0.15, 0.13, 0.11]


def _grey(path_or_img, width):
    import cv2
    im = cv2.imread(path_or_img, cv2.IMREAD_GRAYSCALE) if isinstance(path_or_img, str) else path_or_img
    if im is None:
        return None
    if im.ndim == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    h, w = im.shape[:2]
    if w != width:
        im = cv2.resize(im, (width, max(1, int(h * width / float(w)))),
                        interpolation=cv2.INTER_AREA)
    return im


def fit(frame, reference, ladder=None, floor=FLOOR):
    """(scale, x0, y0, score) in the REFERENCE's own pixels, or None.

    `scale` is the share of the reference's width the moment shows: 1.0 is the
    whole screen, 0.25 is a quarter of it blown up. (x0, y0) is where that crop
    begins in the reference, as a fraction of its width and height.
    """
    import cv2
    ref = _grey(reference, WORK)
    mom = _grey(frame, WORK)
    if ref is None or mom is None:
        return None
    scored = []
    for s in (ladder or LADDER):
        w = max(16, int(WORK * s))
        h = max(16, int(mom.shape[0] * w / float(mom.shape[1])))
        if w > ref.shape[1] or h > ref.shape[0]:
            continue
        small = cv2.resize(mom, (w, h), interpolation=cv2.INTER_AREA)
        r = cv2.matchTemplate(ref, small, cv2.TM_CCOEFF_NORMED)
        _mn, mx, _ml, ml = cv2.minMaxLoc(r)
        scored.append((s, ml[0] / float(ref.shape[1]), ml[1] / float(ref.shape[0]), float(mx)))
    if not scored:
        return None
    # A SMALL TEMPLATE MATCHES BY CHANCE, so the best score alone picks the
    # bottom of the ladder on any frame the reference does not really contain.
    # Measured: a frame plainly showing the whole menu bar came back at 0.11,
    # meaning a ninth of the screen, because a tiny patch finds SOMETHING
    # anywhere. Among the scales that score within a hair of the best, the
    # LARGEST is the honest answer: it is the one explaining the most pixels.
    top = max(x[3] for x in scored)
    if top < floor:
        return None
    near = [x for x in scored if x[3] >= top - 0.05]
    return max(near, key=lambda x: x[0])


def refine(frame, reference, around, span=0.06, steps=7):
    """The same measurement again on a finer ladder round a scale already found."""
    lo, hi = max(0.05, around - span), min(1.0, around + span)
    return fit(frame, reference, ladder=[lo + (hi - lo) * i / (steps - 1.0)
                                         for i in range(steps)])


def unzoomed_by_bar(frame):
    """1.0 where the frame plainly shows the whole menu bar, else None.

    A menu bar runs the full width of the SCREEN, so a frame carrying one from
    edge to edge is showing the whole screen and is not zoomed at all. That is
    a direct reading of the pixels and it beats any search, so it is asked
    first and the search never runs on those frames.
    """
    import cv2
    im = cv2.imread(frame, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    h, w = im.shape[:2]
    strip = im[0:max(6, int(h * 0.028)), :]
    med = float(np.median(strip))
    lit = np.abs(strip.astype(np.int16) - med) > 40
    if lit.mean() < 0.005:
        return None
    # ink must reach both ends: a bar spans the screen, a window's toolbar does not
    cols = lit.any(axis=0)
    on = np.flatnonzero(cols)
    if on.size == 0:
        return None
    if on[0] > 0.06 * w or on[-1] < 0.94 * w:
        return None
    return 1.0


def measure(frame, reference):
    """The zoom for a frame: the bar first, then the search. (scale, x0, y0, score)."""
    bybar = unzoomed_by_bar(frame)
    if bybar is not None:
        return (1.0, 0.0, 0.0, 1.0)
    return fit(frame, reference)
