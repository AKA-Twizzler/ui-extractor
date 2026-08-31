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
import machine
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


def band_of(bands_, y0, y1, bgr=None, x0=None, x1=None):
    """The band a row sits on, if most of the row's height is inside one.

    Given the image and the row's own span, the band must hold THERE too:
    a scan line's median colour can come from a webcam inset on the right
    while the row's own words sit on plain background -- measured on a
    note page, where a "purple band" was the camera, not a highlight.
    """
    for b in bands_:
        top, bottom = max(b["y0"], y0), min(b["y1"], y1)
        if bottom - top < 0.6 * max(1, y1 - y0):
            continue
        if bgr is not None and x0 is not None and x1 > x0:
            region = bgr[max(0, top):bottom, max(0, int(x0)):int(x1)]
            if region.size == 0:
                continue
            med = np.median(region.reshape(-1, 3), axis=0)
            if np.abs(med - np.array(b["colour"])).sum() > 60:
                continue
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
        # a chevron is thin: forty pixels of ink in a cell of four thousand
        if cell.size == 0 or int(cell.sum()) < max(12, 0.008 * cell.size):
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


_POINTER_SCALE = []      # the scale the pointer was last found at, tried first


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
    # THE SCALE IT WAS LAST FOUND AT IS TRIED FIRST AND ALONE. One screen
    # recording has one pointer at one size, so searching five scales on every
    # frame after the first is four searches for nothing -- measured at about
    # four seconds a frame over a whole video. A frame where the remembered
    # scale finds nothing falls back to the full ladder, so a recording that
    # changes size is still read.
    ladder = (0.35, 0.5, 0.75, 1.0, 1.25)
    for ladder in ((tuple(_POINTER_SCALE), ladder) if _POINTER_SCALE else (ladder,)):
      best = None
      for sc in ladder:
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
      if best:
        del _POINTER_SCALE[:]
        _POINTER_SCALE.append(best["scale"])
        return best
    return None


# --------------------------------------------------------- the whole pane

def _box(quad):
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def _rows_of(kind, data):
    """The rows a structure has, each with its box in pane pixels, and the
    dict the style marks go on. The readers measure at different scales:
    the tree at pane size, the document and the list at three times it."""
    if kind == "a file tree":
        return [(r, [r["x0"], r["y0"], r["x1"], r["y1"]], r) for r in data.get("rows") or []]
    if kind == "an open document":
        out = []
        for r in data.get("rows") or []:
            out.append((r, [v / 3 for v in (r["x0"], r["y0"], r["x1"], r["y1"])], r))
        return out
    if kind == "a list of columns":
        out = []
        sc = data.get("scale") or 3
        for b in data.get("blocks") or []:
            b.setdefault("row_style", [{} for _ in b.get("rows") or []])
            for i, box in enumerate(b.get("row_boxes") or []):
                if i < len(b["row_style"]):
                    out.append((b["rows"][i], [v / sc for v in box], b["row_style"][i]))
        return out
    if kind in ("text, not a tree", "only moving video on it"):
        return [(r, r["box"], r) for r in data.get("readings") or []]
    return []


def _name(row):
    if isinstance(row, dict):
        return (row.get("name") or row.get("text") or "").strip()
    if isinstance(row, (list, tuple)):
        return " | ".join(str(c) for c in row).strip()
    return str(row)


def measure(pane_path, kind, data, res):
    """What this pane looks like, attached to its record, said in one line.

    The look (dark or light), the bands rows are painted on, the marks
    before rows, the pictures where no text is, and -- on a document --
    which words lean, which are ruled under, which are links, and whether
    the type is monospace. Every verdict rides on the row it belongs to,
    with the numbers behind it, and the line returned says only what was
    found. None when the pane could not be read.
    """
    img = machine.pixels(pane_path)
    if img is None or data is None:
        return None
    out = {"look": look(img)}
    bd = bands(img)
    out["bands"] = bd
    boxes = [_box(q) for q, _, _ in (res or [])]
    rows = _rows_of(kind, data)
    geo = [{"x0": int(b[0]), "y0": int(b[1]), "x1": int(b[2]), "y1": int(b[3])} for _, b, _ in rows]
    icons = icons_before(img, geo) if geo else []
    said = [f"{out['look']['theme']} look"]
    banded, iconed, icon_hues = [], 0, {}
    for (row, _, mark), g, ic in zip(rows, geo, icons):
        b = band_of(bd, g["y0"], g["y1"], img, g["x0"], g["x1"])
        if b and b["hue"] not in ("black", "white"):
            mark["band"] = b["hue"]
            mark["band_colour"] = b["colour"]
            banded.append((b["hue"], _name(row)[:40]))
        if ic:
            mark["icon"] = ic["hue"]
            mark["icon_box"] = ic["box"]
            iconed += 1
            icon_hues[ic["hue"]] = icon_hues.get(ic["hue"], 0) + 1
    for hue, name in banded[:4]:
        said.append(f"a {hue} band under: {name}")
    if len(banded) > 4:
        said.append(f"and {len(banded) - 4} more banded rows")
    if iconed:
        hues = ", ".join(f"{n} {h}" for h, n in sorted(icon_hues.items(), key=lambda kv: -kv[1]))
        said.append(f"marks before {iconed} rows ({hues})")
    icon_boxes = [ic["box"] for ic in icons if ic]
    pics = pictures(img, boxes + icon_boxes)
    out["pictures"] = pics
    if pics:
        H, W = img.shape[:2]
        p0 = pics[0]
        x0, y0, x1, y1 = p0["box"]
        where = ("top" if y0 < H * 0.25 else "bottom" if y1 > H * 0.75 else "middle")
        side = ("left" if x0 < W * 0.25 else "right" if x1 > W * 0.75 else "centre")
        said.append(f"{len(pics)} picture{'s' if len(pics) > 1 else ''}, the largest "
                    f"{x1 - x0} by {y1 - y0} px at the {where} {side}")
    # a document's type: lean, rules, links, pitch -- on the 3x enlargement
    # the document reader measured on
    if kind == "an open document":
        big = machine.pixels(pane_path.replace(".png", "_3x.png"), cv2.IMREAD_GRAYSCALE)
        if big is not None:
            mask = ink_mask(big)
            italics, ruled, links, mono, total = [], [], [], 0, 0
            for r in data.get("rows") or []:
                cell = mask[int(r["y0"]):int(r["y1"]), int(r["x0"]):int(r["x1"])]
                if cell.size == 0:
                    continue
                total += 1
                xh = float(r.get("xh") or 10)
                words = [(w[0], w[1] - r["x0"], w[2] - r["x0"]) for w in (r.get("words") or [])]
                it = italic_words(cell, words, xh)
                if it:
                    r["italic"] = [w["word"] for w in it]
                    r["italic_slant"] = [w["slant"] for w in it]
                    italics.extend(w["word"] for w in it)
                ul = underline(cell, xh)
                if ul:
                    r["underline"] = ul
                    ruled.append(_name(r)[:40])
                pt = pitch(cell, xh)
                if pt:
                    r["family"] = pt["family"]
                    r["pitch"] = pt["pitch"]
                    if pt["family"] == "monospace":
                        mono += 1
                if r.get("color") == "blue" and (ul or kind == "an open document"):
                    r["link"] = True
                    links.append(_name(r)[:40])
            if italics:
                said.append("italic: " + ", ".join(italics[:6]) + (" and more" if len(italics) > 6 else ""))
            if ruled:
                said.append("ruled under: " + "; ".join(ruled[:3]))
            if links:
                said.append("links (blue): " + "; ".join(links[:3]))
            if total and mono >= 0.7 * total:
                said.append("monospace type")
                out["family"] = "monospace"
            elif total:
                out["family"] = "proportional"
    data["style"] = out
    return "[" + "; ".join(said) + "]"


def blank_pointer(rgb, pad=3):
    """Paint the mouse pointer out of a frame, and say where it was.

    THE POINTER IS NOT THE SCREEN'S INK, and read as if it were it does real
    damage. Three faults in one video traced back to it: `.claude.json` came
    back empty from all three engines because the arrow sits between `claude`
    and `son`; `projects` read `projets` at every moment because the arrow
    covers its `c`; and `04 Dev` read `04 Dev ~` because the arrow's own shape
    reads as a tilde. The first two look like weak engines and the third looks
    like a stray character, and none of them is either.

    What is under the arrow is not recoverable from THIS frame -- it is
    covered -- so the honest thing is to make the patch say nothing rather
    than say something wrong, and let another moment, where the pointer stood
    elsewhere, supply the letters. The ground it is painted with is the median
    of the pixels either side of it in its own band, so the patch matches the
    row it sits in.

    Returns the box painted, or None where no pointer was found. `rgb` is
    changed in place.
    """
    g = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY) if rgb.ndim == 3 else rgb
    got = pointer(g)
    if not got:
        return None
    x0, y0, x1, y1 = got["box"]
    h, w = rgb.shape[:2]
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(w, x1 + pad), min(h, y1 + pad)
    if x1 <= x0 or y1 <= y0:
        return None
    sides = [rgb[y0:y1, max(0, x0 - 40):x0], rgb[y0:y1, x1:min(w, x1 + 40)]]
    near = [a.reshape(-1, a.shape[-1]) for a in sides if a.size]
    if near:
        bg = np.median(np.concatenate(near), axis=0)
    else:
        bg = np.median(rgb[y0:y1].reshape(-1, rgb.shape[-1] if rgb.ndim == 3 else 1), axis=0)
    rgb[y0:y1, x0:x1] = bg.astype(rgb.dtype)
    return [x0, y0, x1, y1]
