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


def _band(lines, pos, a, b, near=3.0):
    """How wide the soft band this edge came back as is, across the line."""
    lo = hi = pos
    for p, la, lb in lines:
        if abs(p - pos) <= near and min(lb, b) - max(la, a) > 0:
            lo, hi = min(lo, p), max(hi, p)
    return lo, hi


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


def _sharpest(grey, lo, hi, a, b, down):
    """Where inside a soft edge the line the screen actually DREW sits.

    A window's side comes with a shadow spread over a dozen pixels, and the
    line finder answers with the whole soft band -- so a box taken from the
    band's outer lip stands a shadow's width outside the window. The window
    is the SHARPEST step in that band, measured along the part of the side
    that is on the screen, so this is a measurement and not a nudge."""
    lo, hi = max(1, int(lo)), min((grey.shape[1] if down else grey.shape[0]) - 2, int(hi))
    if hi <= lo:
        return float(lo), 0.0
    a, b = int(max(0, a)), int(min((grey.shape[0] if down else grey.shape[1]) - 1, b))
    if b - a < 8:
        return float(lo), 0.0
    step = max(1, (b - a) // 200)
    band = grey[a:b:step, lo - 1:hi + 2] if down else grey[lo - 1:hi + 2, a:b:step].T
    d = np.abs(band[:, 2:].astype(np.int32) - band[:, :-2].astype(np.int32)).mean(axis=0)
    i = int(np.argmax(d))
    return float(lo + i), float(d[i])


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
    on the other side.

    The step is only ever over a COVER. An edge is never joined to another
    edge that merely lies along the same line: the two Finder windows have
    their title bars within five working pixels of each other, so chaining
    by nearness alone ran the left one's top across the right one and drew
    it at twice its width."""
    end = float(start)
    while end < limit - max(tol, least):
        probe = (end + 3, pos) if across else (pos, end + 3)
        cov = _covered(probe[0], probe[1], blocks)
        if cov is None:
            return end                      # the side really ended here
        far = float(cov[2] if across else cov[3])
        resumed = [b for p, a, b in lines
                   if abs(p - pos) <= tol and abs(a - far) <= max(tol, least)
                   and b > far]
        # Where the edge does not pick up again, the cover is still hiding
        # it: carry on past the cover rather than calling the cover's own
        # side the window's. What ends the search is running out of frame.
        end = max(resumed) if resumed else far
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

    known = [r[:4] for r in shapes.windows(path)]
    blocks = []
    cam = shapes.camera_box(path)
    cam_w = tuple(v / k for v in cam) if cam else None
    if cam_w:
        blocks.append(cam_w)
    for r in known:
        blocks.append(tuple(v / k for v in r))

    if img is None:
        img = cv2.imread(path) if isinstance(path, str) else path

    least_v, least_h = shapes.RUN * h, shapes.RUN * w
    grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    out = []
    for x, ya, yb in verts:
        side_top, side_bot = _whole_side(verts, x, ya, yb)
        side_lo, side_hi = _band(verts, x, ya, yb)
        for y, xa, xb in hors:
            head_left, head_right = _whole_side(hors, y, xa, xb)
            head_lo, head_hi = _band(hors, y, xa, xb)
            # A WINDOW'S TOP-LEFT CORNER IS WHERE ITS SIDE BEGINS, not
            # merely somewhere its side is crossed. Asking only whether the
            # two edges touch takes every divider inside the window too: the
            # line under the browser's tab strip meets its left edge, and
            # the browser's own back/forward/reload buttons sit three in a
            # row under it, so it passed the corner-buttons test as well and
            # came back as a second window inside the first.
            if abs(y - side_top) > tol or abs(x - head_left) > tol:
                continue
            # A CAMERA IS NOT A WINDOW, and a face passes every test a
            # window's corner passes. The hat brim and the chair back make
            # a corner of two straight edges, and three round features on
            # the face sit in a row inside it -- measured at 00:05:50, that
            # drew a window over the person's head. The camera's own box is
            # already measured; a corner inside it is not a window's.
            if cam_w and cam_w[0] <= x <= cam_w[2] and cam_w[1] <= y <= cam_w[3]:
                continue
            x1 = _run_out(hors, y, head_right, w, blocks, True, tol, least_h)
            y1 = _run_out(verts, x, side_bot, h, blocks, False, tol, least_v)
            # THE REMIT IS THE WINDOW THE SCREEN CUTS OFF -- the one case
            # `shapes` structurally cannot close, because it offers the
            # frame's left and right edges as stand-in sides and offers no
            # such stand-in for its foot. A window whose four edges are all
            # on the screen belongs to `shapes`, and letting this finder
            # answer for it too puts two answers on one window: measured on
            # a desktop shrunk into the middle of the frame, it returned
            # three boxes where there are two, mixing one window's left
            # edge with another's top.
            if x1 < w - tol and y1 < h - tol:
                continue
            if any(abs(r[0] / k - x) <= tol and abs(r[1] / k - y) <= tol
                   for r in known):
                continue                    # ONE HOME: `shapes` measured it
            if (x1 - x) < least_frac * w or (y1 - y) < least_frac * h:
                continue
            x_edge, x_lit = _sharpest(grey, side_lo * k, (side_hi + 1) * k,
                                      side_top * k, side_bot * k, True)
            y_edge, y_lit = _sharpest(grey, head_lo * k, (head_hi + 1) * k,
                                      head_left * k, head_right * k, False)
            if not _corner_buttons(img, x_edge, y_edge):
                continue
            out.append((x_edge, x_lit, y_edge, y_lit,
                        min(W, x1 * k), min(H, y1 * k)))
    # ONE WINDOW, MANY READINGS OF ITS CORNER, and the sharpest wins. A
    # soft edge comes back as several lines, and each pairing refines to a
    # slightly different place: 75, 77 and 80 for one window's left, 186,
    # 196 and 216 for its top. Counting the readings takes the commonest,
    # which here is the browser toolbar's soft under-edge ten pixels above
    # the line Obsidian actually drew. The STRONGEST step is the drawn one.
    near = tol * k
    groups = []
    for c in out:
        for gp in groups:
            if abs(c[0] - gp[0][0]) <= near and abs(c[2] - gp[0][2]) <= near:
                gp.append(c)
                break
        else:
            groups.append([c])
    kept = []
    for gp in groups:
        x0 = max(gp, key=lambda c: c[1])[0]
        y0 = max(gp, key=lambda c: c[3])[2]
        kept.append((x0, y0, max(c[4] for c in gp), max(c[5] for c in gp)))
    kept.sort(key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
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
