#!/usr/bin/env python3
"""Find the windows `shapes` cannot: the maximised or near-full-screen ones.

A window closes in `shapes`/`overlay` only when at least one of its edges can
be drawn corner to corner. A maximised window's edges lie on the screen
boundary and fade into the dark desktop, so it never closes -- the browser
and the Obsidian editor both fail this way at the same moment, and their
content is then read but filed under no window.

They still carry the one mark every window has: the three round buttons at
its top-left. `panes._has_buttons` only VALIDATES a box has them; this FINDS
them -- scanning the frame for a triplet of like-sized, evenly-spaced round
discs sitting in a title-bar strip -- and turns each into a window: the
corner it measured, and a box grown from the window's own ink down and right
of that corner, stopping where the desktop shows through.
"""
import numpy as np

try:
    import cv2
except Exception:                 # pragma: no cover - drawer side has no cv2
    cv2 = None


def _discs(g, blur):
    """Small round discs across the frame, each (cx, cy, radius)."""
    mask = (np.abs(g.astype(np.int16) - blur.astype(np.int16)) > 10).astype(np.uint8)
    n, lab, stats, mids = cv2.connectedComponentsWithStats(mask, 8)
    out = []
    for i in range(1, n):
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        if not (8 <= bw <= 54 and 8 <= bh <= 54):
            continue
        if abs(bw - bh) > 0.4 * max(bw, bh):
            continue                       # not round
        if area < 0.55 * bw * bh:
            continue                       # a ring or a letter, not a disc
        out.append((float(mids[i][0]), float(mids[i][1]), (bw + bh) / 2.0))
    return out


def corners(img, camera=None):
    """Every window top-left the traffic-lights mark, as (x, y) in pixels.

    Gated to drop the menu-bar icon row along the very top, the dock, and the
    camera (a face is a field of round features that mimic buttons), and
    colour-gated to the buttons' own look: three greys (an unfocused window)
    or the classic red / yellow / green."""
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blur = cv2.GaussianBlur(g, (0, 0), 3)

    def in_cam(x, y):
        return camera and camera[0] <= x <= camera[2] and camera[1] <= y <= camera[3]
    discs = [d for d in _discs(g, blur)
             if 0.03 * H < d[1] < 0.85 * H and not in_cam(d[0], d[1])]
    discs.sort(key=lambda d: d[0])
    found = []
    for i in range(len(discs)):
        a0 = discs[i]
        for j in range(i + 1, len(discs)):
            b0 = discs[j]
            if b0[0] - a0[0] > 4 * a0[2]:
                break                      # b already too far right of a
            for k in range(j + 1, len(discs)):
                a, b, c = a0, b0, discs[k]
                if c[0] - b[0] > 4 * max(a[2], b[2], c[2]):
                    break
                if max(abs(a[1] - b[1]), abs(b[1] - c[1])) > 0.5 * max(a[2], b[2], c[2]):
                    continue               # not in one row
                sizes = [a[2], b[2], c[2]]
                if max(sizes) > 1.5 * min(sizes):
                    continue
                one, two = b[0] - a[0], c[0] - b[0]
                if one < 1.1 * max(sizes) or two < 1.1 * max(sizes):
                    continue               # touching -> one shape, not three
                if one > 3.5 * max(sizes) or abs(one - two) > 0.3 * max(one, two):
                    continue               # too far apart, or not even
                sats = [hsv[int(d[1]), int(d[0])][1] for d in (a, b, c)]
                rgb = [img[int(d[1]), int(d[0])][::-1] for d in (a, b, c)]
                greys = all(s < 40 for s in sats)
                r, y, gr = rgb
                classic = (int(r[0]) > 120 and int(r[0]) > int(r[2]) + 20
                           and int(gr[1]) > 100 and int(gr[1]) > int(gr[2]))
                if not (greys or classic):
                    continue
                found.append((a[0] - a[2], a[1] - a[2]))
                break
    uniq = []
    for f in sorted(found):
        if not any(abs(f[0] - u[0]) < 50 and abs(f[1] - u[1]) < 50 for u in uniq):
            uniq.append(f)
    return uniq


def _ink_extent(g, blur, x0, y0, W, H):
    """Grow a box down and right of a corner over the window's own ink,
    stopping where a run of desktop (no ink) says the window has ended.

    The desktop is the near-uniform dark ground the frame sits on; a window
    over it is a raft of ink. Row by row and column by column out from the
    corner, a band with almost no ink for a stretch wider than a window's
    own gaps is the edge of the raft."""
    ink = (np.abs(g.astype(np.int16) - blur.astype(np.int16)) > 8).astype(np.uint8)
    x0i, y0i = int(x0), int(y0)
    # rightmost column still carrying ink in the corner's title-bar band
    band = ink[y0i:y0i + max(8, int(0.02 * H)), x0i:]
    col_ink = band.sum(axis=0)
    right = x0i
    gap = 0
    for x, v in enumerate(col_ink):
        if v > 0:
            right = x0i + x
            gap = 0
        else:
            gap += 1
            if gap > 0.06 * W:
                break
    # bottommost row still carrying ink under the corner's own column
    strip = ink[y0i:, x0i:min(W, right)]
    row_ink = strip.sum(axis=1)
    bottom = y0i
    gap = 0
    for y, v in enumerate(row_ink):
        if v > 0.01 * (right - x0i):
            bottom = y0i + y
            gap = 0
        else:
            gap += 1
            if gap > 0.05 * H:
                break
    return [float(x0i), float(y0i), float(min(W, right)), float(min(H, bottom))]


def big_windows(img, least_frac=0.20):
    """Maximised / near-full-screen windows: (x0, y0, x1, y1) in pixels.

    Only boxes at least `least_frac` of the screen either way are kept -- the
    point of this finder is the big windows `shapes` misses, not another way
    to the small ones it already measures."""
    if cv2 is None:
        return []
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(g, (0, 0), 3)
    out = []
    for cx, cy in corners(img):
        box = _ink_extent(g, blur, cx, cy, W, H)
        if (box[2] - box[0]) >= least_frac * W and (box[3] - box[1]) >= least_frac * H:
            out.append(tuple(box))
    return out


if __name__ == "__main__":
    import sys
    im = cv2.imread(sys.argv[1])
    H, W = im.shape[:2]
    print("corners:", [(round(x / W, 2), round(y / H, 2)) for x, y in corners(im)])
    for b in big_windows(im):
        print("  big window %.2f-%.2f x %.2f-%.2f"
              % (b[0] / W, b[2] / W, b[1] / H, b[3] / H))
