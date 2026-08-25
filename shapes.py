"""Where each window sat on the screen, measured off the frame itself.

The reader measures a window's edges only when it happens to look; the
records mostly hold panes, which are slices of the screen rather than
windows. For a picture of the whole screen to be honest, every window has
to be drawn at the size and shape it really had, so the edges are taken
from the picture of the screen: a window is a rectangle whose four sides
are drawn on the screen as long straight edges.

Nothing here knows the name of any program. A window is found by its
shape alone, so the same rules hold for anything that opens on a screen.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image

SMALL = 960          # the width the frame is looked at, for speed
EDGE = 7.0           # how much light must change across a line to count
RUN = 0.05           # the shortest run of a side, as a share of the frame
MIN_W = 0.10         # a window is at least this wide
MIN_H = 0.06         # and this tall
ALONG = 0.85         # a side must run this much of the window it closes
_CACHE: dict[str, list] = {}


def _grey(path):
    # a path, or the frame itself already in memory: the reader holds its
    # frames as arrays and would otherwise have to write each one to disk
    # just to ask where the windows are
    if hasattr(path, "shape"):
        a = path
        if a.ndim == 3:
            a = a[..., :3].mean(axis=2)
        im = Image.fromarray(a.astype("uint8"), "L")
    else:
        im = Image.open(path).convert("L")
    w, h = im.size
    k = SMALL / float(w)
    im = im.resize((SMALL, max(1, int(round(h * k)))), Image.BILINEAR)
    return np.asarray(im, dtype=np.float32), w, h


def _runs(mask, least):
    """Every run of trues down one line: (start, end), end included."""
    out = []
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return out
    breaks = np.flatnonzero(np.diff(idx) > 2)
    starts = np.r_[0, breaks + 1]
    ends = np.r_[breaks, idx.size - 1]
    for a, b in zip(starts, ends):
        y0, y1 = int(idx[a]), int(idx[b])
        if y1 - y0 + 1 >= least:
            out.append((y0, y1))
    return out


def _sides(g, least_v, least_h):
    """The long straight edges on the screen, down and across. An edge is
    often a soft shadow spread over two or three pixels, so each line is
    looked at together with its neighbours."""
    def widest(a, axis):
        """Each value raised to the largest of itself and its two
        neighbours along one axis - a three-wide maximum, written out so
        this module needs only numpy."""
        prev = np.roll(a, 1, axis=axis)
        nxt = np.roll(a, -1, axis=axis)
        if axis == 1:
            prev[:, 0] = a[:, 0]
            nxt[:, -1] = a[:, -1]
        else:
            prev[0, :] = a[0, :]
            nxt[-1, :] = a[-1, :]
        return np.maximum(np.maximum(a, prev), nxt)

    dv = widest(np.abs(g[:, 2:] - g[:, :-2]), 1)
    dh = widest(np.abs(g[2:, :] - g[:-2, :]), 0)
    verts, hors = [], []
    for x in range(dv.shape[1]):
        for y0, y1 in _runs(dv[:, x] > EDGE, least_v):
            verts.append((x + 1, y0, y1))
    for y in range(dh.shape[0]):
        for x0, x1 in _runs(dh[y, :] > EDGE, least_h):
            hors.append((y + 1, x0, x1))
    return verts, hors


def _thin(lines):
    """One line where several sit within a pixel or two of each other."""
    lines.sort()
    out = []
    for pos, a, b in lines:
        if out and pos - out[-1][0] <= 2 and min(b, out[-1][2]) - max(a, out[-1][1]) > 0:
            p, aa, bb = out[-1]
            out[-1] = (p, min(aa, a), max(bb, b))
        else:
            out.append((pos, a, b))
    return out


def _index(lines, step=8):
    """The lines filed by where they sit, so looking near a place does not
    walk the whole screen's worth of them."""
    shelf = {}
    for line in lines:
        shelf.setdefault(int(line[0]) // step, []).append(line)
    return shelf, step


def _across(shelf, pos, a, b, slack, part, outward, corner=False):
    """The line running along most of a to b nearest `pos`, or None. A
    window's corners are rounded, so its top and bottom sit a little past
    where its sides begin; `outward` says which way to look first.

    The line must also BEGIN and END at the two sides, within the slack a
    rounded corner needs. A line that merely crosses the span belongs to
    something else on the screen - a divider inside another window, a bar
    running the whole width - and pairing it with these two sides invents a
    rectangle whose corners were never drawn."""
    want = part * (b - a)
    ends = max(6.0, 0.03 * (b - a))
    best = None
    lines, step = shelf
    lo, hi = int(pos - slack) // step, int(pos + slack) // step
    for shelf_no in range(lo, hi + 1):
        for p, la, lb in lines.get(shelf_no, ()):
            if abs(p - pos) > slack:
                continue
            if min(b, lb) - max(a, la) < want:
                continue
            if corner and not (a - ends <= la <= a + ends and b - ends <= lb <= b + ends):
                continue        # it does not begin and end at the two sides
            if best is None or (p - pos) * outward > (best - pos) * outward:
                best = p
    return best


def _edge_of_head(shelf, pos, a, b, reach, way, reaches=None):
    """The window's own top (or foot) lying beyond an edge already found.

    The line has to COVER this window's whole width, and it may run a
    little past the sides - a window's shadow spills out beyond it. What
    it may not do is run far past, because a line much longer than the
    window belongs to the screen, not to this window: the desktop bar and
    a divider inside a wider window behind both cross this span, and
    taking either would stretch the window over ground it never had."""
    lines, step = shelf
    ends = max(6.0, 0.03 * (b - a))
    best = None
    lo = int(min(pos, pos + way * reach)) // step
    hi = int(max(pos, pos + way * reach)) // step
    for shelf_no in range(lo, hi + 1):
        for p, la, lb in lines.get(shelf_no, ()):
            if (p - pos) * way <= 0 or (p - pos) * way > reach:
                continue
            if la > a + ends or lb < b - ends:
                continue                      # it does not cover the window
            if lb - la > 1.6 * (b - a) and not (
                    reaches and reaches[0] <= p <= reaches[1]):
                continue                      # far too long to be its edge
            if best is None or (p - pos) * way > (best - pos) * way:
                best = p
    return best


def find(path):
    """Every window on the frame, biggest first, in the frame's own pixels."""
    keyed = isinstance(path, str)
    if keyed and path in _CACHE:
        return _CACHE[path]
    if path is None or (keyed and not os.path.exists(path)):
        return []
    g, W, H = _grey(path)
    h, w = g.shape
    least_v, least_h = int(RUN * h), int(RUN * w)
    verts, hors = _sides(g, least_v, least_h)
    verts, hors = _thin(verts), _thin(hors)
    shelf = _index(hors)
    min_w, min_h = MIN_W * w, MIN_H * h
    # A window pushed off the side of the screen has only ONE side of its
    # own; the screen's edge is where the rest of it went. Without the edge
    # standing in as a side, such a window is never measured at all and has
    # to be guessed at instead. The edge only ever becomes a window's side
    # when that window's top or foot RUNS to it, which is what a window cut
    # off by the screen does and a window sitting short of it does not.
    edges = {0.0, float(w - 1)}
    sides = [(x, ya, yb, False) for x, ya, yb in verts] + \
            [(x, 0.0, float(h), True) for x in edges]
    sides.sort(key=lambda v: v[0])
    found = []
    for i, (x0, ya, yb, e0) in enumerate(sides):
        for x1, yc, yd, e1 in sides[i + 1:]:
            if x1 - x0 < min_w or (e0 and e1):
                continue
            top, bot = max(ya, yc), min(yb, yd)
            if bot - top < min_h:
                continue
            # the screen's edge runs the whole height, so it says nothing
            # about how much of a side this window's own side gave up
            runs = [yb - ya] if not e0 else []
            runs += [yd - yc] if not e1 else []
            share = (bot - top) / max(runs)
            if share < 0.55:
                continue
            slack = max(12, int(0.05 * (bot - top)))
            # A window has at least ONE edge drawn corner to corner - its
            # title bar or its foot. The other need only span the width:
            # an edge can lie along something else on the screen and so run
            # on past the window's own side. Demanding both be exact loses
            # real windows; demanding neither invents rectangles out of a
            # divider inside one window and a side of another.
            top_c = _across(shelf, top, x0, x1, slack, ALONG, -1, corner=True)
            bot_c = _across(shelf, bot, x0, x1, slack, ALONG, +1, corner=True)
            if top_c is None and bot_c is None:
                continue
            y_top = top_c if top_c is not None else _across(shelf, top, x0, x1, slack, ALONG, -1)
            y_bot = bot_c if bot_c is not None else _across(shelf, bot, x0, x1, slack, ALONG, +1)
            if y_top is None or y_bot is None or y_bot - y_top < min_h:
                continue
            tall = y_bot - y_top
            if bot - top < ALONG * tall:
                continue                       # the sides must run its height
            found.append([x0, y_top, x1, y_bot, e0, e1, top, bot])
    found.sort(key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
    # near-identical rectangles are the same window found twice: one edge
    # is a shadow two pixels wide. Rectangles that merely overlap are kept,
    # because two windows may sit one inside the other's reach.
    kept, seen = [], set()
    for r in found:
        key = tuple(int(round(v / 3.0)) for v in r[:4])
        if key in seen:
            continue
        seen.add(key)
        kept.append(r)
    # A window's sides are drawn faintly across its title bar and its
    # toolbar, so the pair of sides can begin BELOW the head of the window
    # and the rectangle come out missing it - a Finder window drawn from
    # its column headers down, its whole top cut away. Where a line runs
    # corner to corner across the SAME two sides above the top found, that
    # line is the window's own top edge, measured like any other, and the
    # rectangle reaches up to it. The same holds under its foot.
    for r in kept:
        x0, y_top, x1, y_bot = r[:4]
        reach = 0.4 * (y_bot - y_top)
        ran = (r[6], r[7]) if len(r) > 7 else (y_top, y_bot)
        for side, way in ((1, -1), (3, +1)):
            # how far the window's own SIDES ran: a line the sides reach is
            # that window's own edge however far it goes on past it, where
            # a line lying well beyond them belongs to the screen
            end = ran[0] if way < 0 else ran[1]
            slack_e = max(4.0, 0.03 * (y_bot - y_top))
            edge = _edge_of_head(shelf, r[side], x0, x1, reach, way,
                                 reaches=(end - slack_e, end + slack_e))
            if edge is None or (edge - r[side]) * way <= 2:
                continue
            lo, hi = min(edge, r[side]), max(edge, r[side])
            # nothing else the frame measured may stand in the way: a foot
            # in that band belongs to a window in front, not to this one
            blocked = False
            for o in kept:
                if o is r or min(o[2], x1) - max(o[0], x0) <= 0.5 * (x1 - x0):
                    continue
                if lo + 2 < o[1] < hi - 2 or lo + 2 < o[3] < hi - 2:
                    blocked = True
                    break
            if not blocked:
                r[side] = edge
    # The screen's edge stood in for a side. Where a window with a side of
    # its OWN sits against the same top and foot and ends before the edge,
    # the edge rectangle reached past that window and swallowed whatever
    # lay beyond it - two windows read as one. The real-sided one is the
    # window; the edge one is dropped. This runs after the heads are put
    # back on, so the two are compared at their true tops.
    drop = set()
    for r in kept:
        x0, yt, x1, yb, e0, e1 = r
        if not (e0 or e1):
            continue
        tall, wide = max(1.0, yb - yt), max(1.0, x1 - x0)
        step = max(3.0, 0.01 * wide)
        for o in kept:
            if o is r or (o[4] and o[5]):
                continue
            if abs(o[1] - yt) > 0.06 * tall or abs(o[3] - yb) > 0.06 * tall:
                continue
            if e1 and not o[5] and abs(o[0] - x0) <= 0.06 * wide and o[2] < x1 - step:
                drop.add(id(r))
                break
            if e0 and not o[4] and abs(o[2] - x1) <= 0.06 * wide and o[0] > x0 + step:
                drop.add(id(r))
                break
    kept = [r for r in kept if id(r) not in drop]
    kept = [r[:4] for r in kept]
    # A window the video caught mid-scroll is drawn on the frame in slabs:
    # the parts that were painted, with a band of unpainted screen between
    # them. Those slabs stand on the same two sides with nothing measured
    # between them, so they are one window and the window is the whole of
    # it. Left as slabs, a window is drawn as a third of its real height.
    joined, used = [], set()
    for i, a in enumerate(kept):
        if i in used:
            continue
        box = list(a)
        for j, b in enumerate(kept):
            if j <= i or j in used:
                continue
            wide = max(box[2] - box[0], b[2] - b[0])
            if abs(b[0] - box[0]) > 0.02 * wide or abs(b[2] - box[2]) > 0.02 * wide:
                continue                       # not standing on the same sides
            lo, hi = min(box[3], b[3]), max(box[1], b[1])
            if hi <= lo:
                continue                       # they already touch or overlap
            if hi - lo > 2.5 * ((box[3] - box[1]) + (b[3] - b[1])):
                continue                       # too far apart to be one window
            if any(c is not a and c is not b and lo < (c[1] + c[3]) / 2 < hi
                   and min(box[2], c[2]) - max(box[0], c[0]) > 0.5 * wide
                   for c in kept):
                continue                       # something else stands between
            used.add(j)
            box[1], box[3] = min(box[1], b[1]), max(box[3], b[3])
        joined.append(box)
    kept = joined
    k = W / float(w)
    out = [[r[0] * k, r[1] * k, r[2] * k, r[3] * k] for r in kept]
    if keyed:
        _CACHE[path] = out
    return out


def _shares(a, b):
    """How much of the smaller rectangle the two have in common."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (w * h) / max(1.0, small)


def frame_of(m):
    """The picture of the screen for this moment, if it is still on disk."""
    p = m.get("frame")
    if p and "\\" in p:
        p = "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    return p if p and os.path.exists(p) else None


_CAM: dict[str, object] = {}


def _blocks(mask):
    """Number the runs of touching true squares in a small grid: the same
    answer a labelling library gives, worked out here so the drawing side of
    the tool needs nothing installed beyond what reads the pictures."""
    h, w = mask.shape
    lab = np.zeros((h, w), dtype=np.int32)
    n = 0
    for sy in range(h):
        for sx in range(w):
            if not mask[sy, sx] or lab[sy, sx]:
                continue
            n += 1
            stack = [(sy, sx)]
            lab[sy, sx] = n
            while stack:
                y, x = stack.pop()
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = n
                        stack.append((ny, nx))
    return lab, n


def camera_box(path):
    """The camera picture laid over the screen, found by its colour: a
    screen's furniture is nearly grey, a camera's picture is not.

    Counting one unbroken patch of colour is too brittle to trust: a face,
    dark hair and a shadow break the camera's picture into pieces, and the
    same camera then passes at one moment and fails at the next. So the
    frame is scored in coarse squares instead - a square counts when a
    third of it is colourful - and the largest block of touching squares is
    the camera. Small colourful marks (an icon, a selection band) never
    fill a block that wide and that tall, so they fall out on their own."""
    if path in _CAM:
        return _CAM[path]
    if not path or not os.path.exists(path):
        return None
    im = Image.open(path).convert("RGB")
    W, H = im.size
    im = im.resize((320, max(1, int(320 * H / W))), Image.BILINEAR)
    a = np.asarray(im, dtype=np.int16)
    sat = a.max(axis=2) - a.min(axis=2)
    mask = (sat > 45)
    sh, sw = mask.shape
    cell = 8
    gh, gw = sh // cell, sw // cell
    grid = mask[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).mean(axis=(1, 3))
    lab, n = _blocks(grid > 0.33)
    best = None
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        w, h = (x1 - x0 + 1) / gw, (y1 - y0 + 1) / gh
        if w < 0.12 or h < 0.12 or w * h < 0.03:
            continue
        if ys.size / ((y1 - y0 + 1) * (x1 - x0 + 1)) < 0.5:
            continue
        if best is None or ys.size > best[0]:
            best = (ys.size, [x0 * cell, y0 * cell, (x1 + 1) * cell, (y1 + 1) * cell])
    out = None
    if best:
        k = W / 320.0
        out = [v * k for v in best[1]]
    _CAM[path] = out
    return out
