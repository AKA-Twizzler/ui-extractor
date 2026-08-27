#!/usr/bin/env python3
"""Find the windows `shapes` cannot: the ones the SCREEN cuts off.

`shapes` closes a window from a pair of vertical sides plus a top and a
foot. It already lets the frame's LEFT and RIGHT edges stand in as sides,
so a window pushed off the side of the screen is measured. It offers no
such stand-in for a window pushed off the FOOT of the screen, and that is
the whole reason the browser and the Obsidian editor were never measured:
their top and left edges are drawn plainly, their right and foot are the
screen's own boundary, and with no foot to find the rectangle never closes.

So this finds a window the other way round -- from the CORNER its two
drawn edges make, and outward to wherever those edges end.
"""
import numpy as np

try:
    import cv2
except Exception:                 # pragma: no cover - the drawer has no cv2
    cv2 = None

import shapes


def _corner_buttons(img, x0, y0):
    """The three round buttons at a window's own top-left, looked for in a
    strip sized by the BUTTONS rather than by the window.

    `panes._has_buttons` sizes its strip as a share of the box it is given,
    which is right for a small window and wrong for a big one: on a window
    filling the screen that share is a 1128x275 slab holding the toolbar,
    the tab and the top of the tree, and its median is no longer the title
    bar's own ground. A title bar stands the same height whatever the
    window's width, so the strip is measured in pixels of the frame."""
    H, W = img.shape[:2]
    k = W / 3840.0                      # the fixtures are 4K; scale with the frame
    sw, sh = int(420 * k), int(130 * k)
    x0, y0 = int(round(x0)), int(round(y0))
    strip = img[max(0, y0):y0 + sh, max(0, x0):x0 + sw]
    if strip.size == 0 or strip.shape[0] < 8 or strip.shape[1] < 24:
        return False
    g = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY)
    back = float(np.median(g))
    mask = (np.abs(g.astype(np.int16) - back) > 14).astype(np.uint8)
    n, lab, stats, mids = cv2.connectedComponentsWithStats(mask, 8)
    blobs = []
    for i in range(1, n):
        bw, bh = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        area = int(stats[i, cv2.CC_STAT_AREA])
        if bw < 4 or bh < 4 or bw > 0.25 * strip.shape[1]:
            continue
        if abs(bw - bh) > 0.45 * max(bw, bh):
            continue                       # not round
        if area < 0.45 * bw * bh:
            continue                       # a ring or a letter, not a disc
        blobs.append((float(mids[i][0]), float(mids[i][1]), (bw + bh) / 2.0))
    # THREE DISCS IN ONE ROW, and the row has to be picked out FIRST. A
    # sliding triple over an x-sorted list is not the same question: the
    # ribbon icon sitting a row below the buttons sorts BETWEEN them, so
    # every triple that contains it fails "in one row" and the buttons are
    # never tested as a group at all. Gather each blob's own row, then ask.
    for seed in blobs:
        row = sorted(b for b in blobs
                     if abs(b[1] - seed[1]) <= 0.6 * max(b[2], seed[2]))
        for i in range(len(row) - 2):
            a, b, c = row[i:i + 3]
            if a[0] > 0.30 * strip.shape[1] or a[1] > 0.75 * strip.shape[0]:
                continue                   # not in the corner
            sizes = [a[2], b[2], c[2]]
            if max(sizes) > 1.5 * min(sizes):
                continue
            one, two = b[0] - a[0], c[0] - b[0]
            if one < max(sizes) or two < max(sizes):
                continue                   # touching, so one shape not three
            if abs(one - two) > 0.35 * max(one, two):
                continue                   # not evenly spaced
            return True
    return False


def _whole_side(lines, pos, a, b, near=3.0):
    """One drawn edge, gathered from every segment of itself.

    An edge two or three pixels wide comes back as several runs at
    neighbouring positions, and each run may be broken in a different
    place. Asked about any one of them, "where does this side begin" gets
    a different answer each time -- and the answer matters, because it is
    what tells a window's own TOP-LEFT CORNER from a T-junction where its
    furniture meets its left edge. A window's side stops at its top; the
    browser's left edge runs on ABOVE the line under its tab strip, which
    is how that divider came back as a second window."""
    lo, hi = a, b
    for p, la, lb in lines:
        if abs(p - pos) <= near and min(lb, b) - max(la, a) > 0:
            lo, hi = min(lo, la), max(hi, lb)
    return lo, hi


def _covered(x, y, blocks):
    for bx0, by0, bx1, by1 in blocks:
        if bx0 - 1 <= x <= bx1 + 1 and by0 - 1 <= y <= by1 + 1:
            return (bx0, by0, bx1, by1)
    return None


def _run_out(lines, pos, start, limit, blocks, across, tol, least):
    """How far one drawn edge reaches, counting what merely COVERS it.

    An edge stops for two different reasons and they mean opposite things.
    It stops because the window stops -- that is the window's corner. Or it
    stops because something stands in front of it, and then it has not
    ended at all: the trace steps over the cover and picks the same edge up
    on the other side. Where the cover runs on to the frame's own boundary
    there is nothing left that could end the window, so the boundary is the
    answer -- which is what a person reading the screen concludes too."""
    end = start
    while True:
        best = end
        for p, a, b in lines:
            if abs(p - pos) > tol:
                continue
            if a <= end + tol and b > best:
                best = b
        if best > end:
            end = best
        if end >= limit - tol:
            return float(limit)
        probe = (end + 3, pos) if across else (pos, end + 3)
        cov = _covered(probe[0], probe[1], blocks)
        if cov is None:
            return float(end)
        end = (cov[2] if across else cov[3])     # step over the cover
        # WHAT IS LEFT MUST BE BIG ENOUGH TO SHOW AN EDGE. Past the cover
        # there may be less frame left than the shortest run this instrument
        # can see, and a strip that cannot hold an edge cannot show one
        # either way. The boundary stands, because nothing else can.
        if end >= limit - max(tol, least):
            return float(limit)


def big_windows(path, least_frac=0.20, img=None):
    """Windows the screen cuts off, as (x0, y0, x1, y1) in the frame's own
    pixels, biggest first.

    Each is a corner where a drawn top edge meets a drawn left edge, grown
    to wherever those two edges end, and confirmed by the three round
    buttons every window carries at that corner."""
    if cv2 is None:
        return []
    g, W, H = shapes._grey(path)
    h, w = g.shape
    verts, hors = shapes._sides(g, int(shapes.RUN * h), int(shapes.RUN * w))
    verts, hors = shapes._thin(verts), shapes._thin(hors)
    k = W / float(w)
    tol = max(4.0, 0.008 * w)

    blocks = []
    cam = shapes.camera_box(path)
    if cam:
        blocks.append(tuple(v / k for v in cam))
    for r in shapes.windows(path):
        blocks.append(tuple(v / k for v in r[:4]))

    if img is None:
        img = cv2.imread(path) if isinstance(path, str) else path

    least_v, least_h = shapes.RUN * h, shapes.RUN * w
    out = []
    for x, ya, yb in verts:
        side_top, side_bot = _whole_side(verts, x, ya, yb)
        for y, xa, xb in hors:
            head_left, head_right = _whole_side(hors, y, xa, xb)
            # A WINDOW'S TOP-LEFT CORNER IS WHERE ITS SIDE BEGINS, not
            # merely somewhere its side is crossed. Asking only whether the
            # two edges touch takes every divider inside the window too: the
            # line under the browser's tab strip meets its left edge, and
            # the browser's own back/forward/reload buttons sit three in a
            # row under it, so it passed the corner-buttons test as well and
            # came back as a second window inside the first.
            if abs(y - side_top) > tol or abs(x - head_left) > tol:
                continue
            x1 = _run_out(hors, y, head_right, w, blocks, True, tol, least_h)
            y1 = _run_out(verts, x, side_bot, h, blocks, False, tol, least_v)
            if x1 < w - tol and y1 < h - tol:
                continue                    # not cut off: `shapes` owns it
            if (x1 - x) < least_frac * w or (y1 - y) < least_frac * h:
                continue
            box = (x * k, y * k, min(W, x1 * k), min(H, y1 * k))
            if not _corner_buttons(img, box[0], box[1]):
                continue
            out.append(box)
    kept = []
    for b in sorted(out, key=lambda b: -(b[2] - b[0]) * (b[3] - b[1])):
        if any(abs(b[0] - u[0]) < 0.02 * W and abs(b[1] - u[1]) < 0.02 * H
               for u in kept):
            continue
        kept.append(b)
    return kept


if __name__ == "__main__":
    import sys
    p = sys.argv[1]
    im = cv2.imread(p)
    H, W = im.shape[:2]
    for b in big_windows(p, img=im):
        print("  big window  %.3f-%.3f x  %.3f-%.3f   px %s"
              % (b[0] / W, b[2] / W, b[1] / H, b[3] / H,
                 tuple(int(round(v)) for v in b)))
