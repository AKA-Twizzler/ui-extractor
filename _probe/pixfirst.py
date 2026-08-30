"""Pixels first, words second: one Finder list window read from its picture.

The structure comes from the pixels alone -- the window's rectangle, the
sidebar's dividing line, the toolbar and header bands, the rows from the
list's own stripes, the selected band from its colour, the icons from
their colour, the columns from the header's words, the thumb from its
bar -- and only then are the words read, row by row, into that structure.
Run under the Windows venv (cv2, rapidocr):
    python _probe/pixfirst.py <frame.png> <out_dir> [<title>]
"""
import json, os, re, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shapes

_ENGINE = None
def engine():
    global _ENGINE
    if _ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _ENGINE = RapidOCR()
    return _ENGINE

def load(path):
    im = Image.open(path).convert("RGB")
    rgb = np.asarray(im)
    g = np.asarray(im.convert("L"), dtype=np.float32)
    return rgb, g

def ocr(rgb_crop, scale=2.0):
    """The words in a crop, upscaled for the engine: [(x0,y0,x1,y1,text,score)] in the crop's own pixels.
    The contrast is stretched first: a dimmed window's grey writing on grey is nothing to the engine as it stands."""
    from PIL import ImageOps
    im = ImageOps.autocontrast(Image.fromarray(rgb_crop), cutoff=1)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    arr = np.asarray(im)[:, :, ::-1].copy()      # BGR for the engine
    res, _ = engine()(arr)
    out = []
    for box, text, score in (res or []):
        xs = [p[0] / scale for p in box]; ys = [p[1] / scale for p in box]
        out.append((min(xs), min(ys), max(xs), max(ys), text, float(score)))
    return out


def ink_mask(rgb_region, floor=55, lift=30):
    """The writing in a region: pixels whose darkest channel stands `lift`
    above the region's own background (the median), never under `floor`,
    so a dimmed window's grey writing counts as its white does. A column
    lit without a break over more than a fifth of the region's height is a
    line or a bar (a sidebar's thumb standing inside a list's box), never
    writing, and is dropped."""
    mn = rgb_region.min(axis=2)
    # the background is each row's own median: a selected row's band is
    # background to the white writing on it, not writing itself
    med = np.median(mn, axis=1, keepdims=True)
    thr = np.maximum(float(floor), med + lift)
    ink = mn > thr
    h = ink.shape[0]
    if h >= 8:
        # the longest unbroken run of lit rows in each column
        run = np.zeros(ink.shape[1], dtype=int)
        best = np.zeros(ink.shape[1], dtype=int)
        for y in range(h):
            run = np.where(ink[y], run + 1, 0)
            best = np.maximum(best, run)
        # a row of writing is thirty rows deep at most; a bar runs far past that
        ink[:, best > max(0.2 * h, 60)] = False
    return ink

def steps(profile, least=6.0):
    """Where a 1-D profile steps by at least `least`: [(index, delta)]."""
    d = np.diff(profile)
    return [(i + 1, float(d[i])) for i in range(len(d)) if abs(d[i]) >= least]

def window_box(path, g, title_hint=None):
    """The window to read: the biggest rectangle the frame closes that touches the left edge (a window the crop cut), else the biggest."""
    try:
        wins = shapes.windows(path)
    except Exception:
        wins = []
    wins = [list(map(float, w[0] if isinstance(w, (list, tuple)) and len(w) == 2 and isinstance(w[0], (list, tuple)) else w)) for w in wins]
    wins = [w for w in wins if len(w) == 4 and (w[2] - w[0]) > 0.3 * g.shape[1]]
    if not wins:
        return None
    cut = [w for w in wins if w[0] < 0.03 * g.shape[1]]
    pick = max(cut or wins, key=lambda w: (w[2] - w[0]) * (w[3] - w[1]))
    return [int(v) for v in pick]

def divider(g, wb):
    """The sidebar's dividing line: the biggest DOWNWARD step in the column
    means across the window's left half (the sidebar is the lighter shade);
    none found, the window's own left edge (the crop cut the sidebar off)."""
    x0, y0, x1, y1 = wb
    band = g[y0 + int(0.2 * (y1 - y0)):y1 - int(0.1 * (y1 - y0)), x0:x0 + int(0.45 * (x1 - x0))]
    col = np.median(band, axis=0)          # the median: words are sparse, the background is not
    # the list's icons stand in every row, so their column is bright in the
    # median: the divider is left of the first such column
    bright = [i for i, v in enumerate(col) if v > 100 and i > 8]
    if bright:
        col = col[:max(9, bright[0] - 10)]
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    # a step down from a sidebar's shade (not from a column of icons,
    # which is far brighter than any background)
    st = [(i, d) for i, d in steps(sm, 2.5) if d < 0 and i > 8 and 35 <= sm[max(0, i - 6)] <= 90]
    if not st:
        return x0
    i, d = min(st, key=lambda s: s[1])
    return x0 + i

def ink_bands(rgb, xl, x1, y0, y1, least=2):
    """The rows of writing on the list side, from the ink itself: runs of
    rows holding light pixels (text and white icons; a green band's own
    colour is not ink). [(top, bottom)] in frame pixels."""
    # the bar at the right edge is not ink: stop sixty short of it
    c = rgb[y0:y1, xl + 20:x1 - 60]
    ink = ink_mask(c)
    cnt = ink.sum(axis=1).astype(int)
    cnt[cnt > 0.6 * ink.shape[1]] = 0        # a line across the width is a border, not writing
    # the rows between the writing carry a little ink of their own (a
    # stroke of an icon, a mark): the least is a step above that level
    base = int(np.percentile(cnt, 25)) if len(cnt) else 0
    # a selected row's band carries a few light pixels on its own rows;
    # writing carries hundreds
    least = max(least, 12, base + 12, int(0.04 * np.percentile(cnt, 90)) if len(cnt) else 0)
    out, start = [], None
    for i, v in enumerate(cnt):
        if v > least and start is None:
            start = i
        elif v <= least and start is not None:
            out.append([start, i]); start = None
    if start is not None:
        out.append([start, len(cnt)])
    merged = []
    for a, b in out:
        if merged and a - merged[-1][1] < 6:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(y0 + a, y0 + b) for a, b in merged if b - a >= 6]

def find_header(rgb, xl, x1, wb):
    """The header band: the first band of writing under the toolbar that reads Name / Date Modified / Size / Kind; returns (top, bottom, columns)."""
    x0, y0, x1_, y1 = wb
    for (a, b) in ink_bands(rgb, xl, x1, y0, y0 + (y1 - y0) // 3)[:4]:
        words = ocr(rgb[a - 4:b + 4, xl:x1], 2.0)
        texts = [w[4].strip() for w in words]
        joined = " ".join(texts).lower()
        if "name" in joined or "modified" in joined or "kind" in joined:
            # the column lefts from the header's own ink: runs of columns
            # holding light pixels, split at gaps of thirty or more
            band = rgb[a:b, xl:x1]
            ink = ink_mask(band).sum(axis=0)
            groups, start = [], None
            for i, v in enumerate(ink):
                if v > 0 and start is None:
                    start = i
                elif v == 0 and start is not None:
                    groups.append([start, i]); start = None
            if start is not None:
                groups.append([start, len(ink)])
            merged = []
            for s_, e_ in groups:
                if merged and s_ - merged[-1][1] < 30:
                    merged[-1][1] = e_
                else:
                    merged.append([s_, e_])
            merged = [(s_, e_) for s_, e_ in merged if e_ - s_ >= 35]     # a sort chevron is no column
            # a bar's stub or a divider standing in the header's band is a
            # solid block, every column of it lit from the band's top to its
            # bottom; a heading's letters vary in height column by column
            ink2 = ink_mask(band)
            solid = lambda s_, e_: (ink2[:, s_:e_].mean(axis=0) >= 0.9).mean() >= 0.9
            merged = [(s_, e_) for s_, e_ in merged if not solid(s_, e_)]
            cols = []
            for s_, e_ in merged:
                got = ocr(rgb[max(0, a - 6):b + 6, max(0, xl + s_ - 10):xl + e_ + 10], 3.0)
                cols.append((xl + s_, " ".join(w[4] for w in sorted(got, key=lambda w: w[0])).strip()))
            return a, b, cols
    return None, None, []

def bottom_border(g, wb, xl):
    """The window's bottom border or the pathbar's line: a thin run of rows
    (eight at most) in the window's bottom seventh, even across the list's
    width and a step lighter than the dark rows around it. A selected row's
    band is even too, but sixty rows deep."""
    x0, y0, x1, y1 = wb
    h = y1 - y0
    xs = slice(xl + 40, x1 - 60)
    ys_ = list(range(max(0, y1 - int(0.15 * h)), min(g.shape[0], y1 + int(0.06 * h))))
    if len(ys_) < 3:
        return y1
    rows = g[ys_[0]:ys_[-1] + 1, xs]
    means = rows.mean(axis=1)
    spread = np.percentile(rows, 95, axis=1) - np.percentile(rows, 5, axis=1)
    even = spread < 25
    i = 0
    while i < len(ys_):
        if even[i]:
            j = i
            while j + 1 < len(ys_) and even[j + 1]:
                j += 1
            if j - i + 1 <= 8 and i >= 4 and j + 5 <= len(ys_):
                # a line stands a step above the rows on both sides of it
                above = float(np.median(means[i - 4:i])); below = float(np.median(means[j + 1:j + 5]))
                if float(means[i:j + 1].max()) > max(above, below) + 10:
                    return ys_[i]
            i = j + 1
        else:
            i += 1
    return y1

def word_crops(rgb, ya, yb, ca, cb, gap=10):
    """A cell's words as separate crops, split at gaps of `gap` columns
    with no ink: [(x0, x1)] in frame pixels."""
    band = rgb[ya:yb, ca:cb]
    ink = ink_mask(band).sum(axis=0)
    runs, start = [], None
    for i, v in enumerate(ink):
        if v > 0 and start is None:
            start = i
        elif v == 0 and start is not None:
            runs.append([start, i]); start = None
    if start is not None:
        runs.append([start, len(ink)])
    merged = []
    for s_, e_ in runs:
        if merged and s_ - merged[-1][1] < gap:
            merged[-1][1] = e_
        else:
            merged.append([s_, e_])
    return [(ca + s_, ca + e_) for s_, e_ in merged if e_ - s_ >= 4]

def _join(got, height):
    """The engine's pieces in reading order, a space where the gap between
    two pieces is a third of the writing's height or more."""
    got = sorted(got, key=lambda w: w[0])
    out = ""
    for i, w in enumerate(got):
        if i and (w[0] - got[i - 1][2]) >= 0.3 * height:
            out += " "
        out += w[4].strip()
    return out.strip()

_FOLD = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
_MARKS = lambda s: s.count("_") + s.count(".") + s.count(",") + s.count(":")

def _ratio(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0

def _medoid(cands):
    """The reading most like the others, once folded to letters and digits;
    the index into cands, or None when every reading is empty."""
    folds = [_FOLD(c) for c in cands]
    best_i, best_s = None, -1.0
    for i, f in enumerate(folds):
        if not f:
            continue
        s = sum(_ratio(f, g_) for j, g_ in enumerate(folds) if j != i and g_)
        if s > best_s:
            best_i, best_s = i, s
    return best_i

def _respace(txt, alt):
    """txt's letters with alt's spaces, where the two hold the same letters."""
    ft, fa = _FOLD(txt), _FOLD(alt)
    if len(ft) != len(fa) or " " in txt or " " not in alt:
        return txt
    cuts, n = set(), 0
    for ch in alt:
        if ch == " ":
            cuts.add(n)
        elif re.match(r"[a-z0-9]", ch.lower()):
            n += 1
    out, n = "", 0
    for ch in txt:
        if n in cuts and n and not out.endswith(" "):
            out += " "; cuts.discard(n)
        out += ch
        if re.match(r"[a-z0-9]", ch.lower()):
            n += 1
    return out

_WEIGHT = lambda s: 2 * s.count("_") + s.count(".") + s.count(",") + s.count(":")

def _rapid_text(crop, scale, height):
    got = ocr(crop, scale)
    return _join(got, height), [w[5] for w in got]

def read_cell(rgb, ya, yb, ca, cb, twice=False):
    """A cell's text by majority. A name (twice=True) is one crop over the
    whole of its ink, read by the first engine at two sizes and by the
    second engine once; the reading most like the other two stands, with
    the second engine's underscores and spaces laid over it where its
    letters agree. Any other cell is read whole at two sizes, word by word
    (each word cropped with its own margin, padded with background), and by
    the second engine; the reading most like the others stands, and a date
    or a size then takes the shape Finder writes it in. Returns (text, mean
    confidence, the count of words the engine could not read)."""
    H = rgb.shape[0]
    boxes = word_crops(rgb, ya, yb, ca, cb)
    if not boxes:
        return "", 0.0, 0
    y0_, y1_ = max(0, ya - 6), min(H, yb + 6)
    height = max(8, yb - ya)
    x0_, x1_ = max(ca, boxes[0][0] - 14), min(cb, boxes[-1][1] + 14)
    whole_crop = rgb[y0_:y1_, x0_:x1_]
    r3, s3 = _rapid_text(whole_crop, 3.0, height)
    r2, s2 = _rapid_text(whole_crop, 2.0, height)
    alt = re.sub(r"\s+", " ", tess_word(whole_crop)).strip()
    if twice:
        cands = [r3, r2, alt]
        i = _medoid(cands)
        if i is None:
            return "", 0.0, 1
        txt = cands[i]
        scores = s3 if i == 0 else (s2 if i == 1 else (s3 or s2))
        if alt and txt is not alt and _ratio(_FOLD(alt), _FOLD(txt)) >= 0.85:
            if _WEIGHT(alt) > _WEIGHT(txt):
                txt = alt                    # the second engine keeps the underscores
            else:
                txt = _respace(txt, alt)     # and the spaces
        txt = re.sub(r"^[^A-Za-z0-9._~$]+", ".", txt)      # a hidden file's leading dot, read as a dash or a comma
        txt = re.sub(r"\. (?=[a-z])", ".", txt)             # no space after a dot inside a name
        if os.environ.get("PF_DEBUG"):
            print("   name", repr(r3), repr(r2), repr(alt), "->", repr(txt))
        return txt, (float(np.mean(scores)) if scores else 0.0), (0 if txt else 1)
    words, scores, blank = [], [], 0
    for i, (wa, wb_) in enumerate(boxes):
        lg = (wa - boxes[i - 1][1]) if i else 100
        rg = (boxes[i + 1][0] - wb_) if i + 1 < len(boxes) else 100
        ml, mr = min(14, max(3, lg // 2)), min(14, max(3, rg // 2))
        crop = rgb[y0_:y1_, max(ca, wa - ml):min(cb, wb_ + mr)]
        crop = np.pad(crop, ((0, 0), (14 - ml, 14 - mr), (0, 0)), mode="edge")
        got = ocr(crop, 3.0 if (wb_ - wa) > 40 else 4.0)
        w_ = "".join(w[4] for w in sorted(got, key=lambda w: w[0])).strip()
        if w_:
            words.append(w_); scores.extend(w[5] for w in got)
        else:
            blank += 1
    pw = " ".join(words)
    cands = [r3, r2, pw, alt]
    i = _medoid(cands)
    if i is None:
        return "", 0.0, blank
    text = cands[i]
    scores = [s3, s2, scores, s3 or s2][i]
    if alt and text is not alt and _ratio(_FOLD(alt), _FOLD(text)) >= 0.85 and _WEIGHT(alt) >= _WEIGHT(text):
        text = alt                           # the second engine keeps the commas
    shaped = finder_shape(text)
    if shaped is None:
        for c in cands:
            if c and c is not text and _ratio(_FOLD(c), _FOLD(text)) >= 0.85:
                shaped = finder_shape(c)
                if shaped is not None:
                    break
    if os.environ.get("PF_DEBUG"):
        print("   cell", [repr(c) for c in cands], "->", repr(shaped if shaped is not None else text))
    return (shaped if shaped is not None else text), (float(np.mean(scores)) if scores else 0.0), blank

def finder_shape(s):
    """A date or a size in the shape Finder writes it, from a reading that
    holds the letters and digits but not the spaces: "Jun 30, 2026 at 5:54
    PM", "Today at 8:47 PM", "57 KB". None where the reading is neither."""
    f = re.sub(r"\s+", "", s)
    m = re.fullmatch(r"([A-Z][a-z]{2})(\d{1,2})[,.]?(\d{4})(?:at)?(\d{1,2})[:;.](\d{2})(AM|PM)", f)
    if m:
        return "%s %s, %s at %s:%s %s" % m.groups()
    m = re.fullmatch(r"(Today|Yesterday)(?:at)?(\d{1,2})[:;.](\d{2})(AM|PM)", f)
    if m:
        return "%s at %s:%s %s" % m.groups()
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(bytes|KB|MB|GB|TB)", f)
    if m:
        return "%s %s" % m.groups()
    if f == "--":
        return "--"
    return None

def _close(a, b):
    if not a or not b:
        return False
    if abs(len(a) - len(b)) > max(2, len(a) // 8):
        return False
    n = min(len(a), len(b))
    diff = sum(1 for x, y in zip(a[:n], b[:n]) if x != y) + abs(len(a) - len(b))
    return diff <= max(2, len(a) // 6)

def tess_word(rgb_crop):
    """One word read by the second engine: enlarged four times, turned to
    dark writing on light paper, one line (psm 7)."""
    try:
        import cv2, verify_names
    except Exception:
        return ""
    # the darkest channel: white writing on a green or blue band stands
    # as high as it does on black, and the band as low
    im = Image.fromarray(rgb_crop.min(axis=2).astype(np.uint8))
    im = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    g = np.asarray(im)
    ink = (255 - g) if float(np.median(g)) < 128 else g
    try:
        return verify_names._tess_line(np.ascontiguousarray(ink), psm=7)
    except Exception:
        return ""

def icon_of(rgb, y0, y1, x0, x1):
    """What the icon at a row's head is, by its colour: folder (green), md
    (a cream page with an orange fold), file (a white page), or none."""
    c = rgb[y0 + 4:y1 - 4, x0:x1].astype(np.float32)
    if c.size == 0:
        return "none", 0
    r, gg, b = c[:, :, 0], c[:, :, 1], c[:, :, 2]
    lit = c.max(axis=2) > 90
    green = int(((gg > r + 40) & (gg > b + 40) & (gg > 110)).sum())
    orange = int(((r > 170) & (gg > 70) & (gg < 190) & (b < 110)).sum())
    if green >= 30:
        return "folder", green
    if orange >= 15:
        return "md", orange
    if lit.mean() > 0.05:
        return "file", int(lit.sum())
    return "none", 0

def read_frame(path, out_dir=None, title_hint="memory", wb=None, list_box=False):
    rgb, g = load(path)
    H, W = g.shape
    if wb:
        wb = [int(v) for v in wb]
    else:
        wb = window_box(path, g, title_hint) or [0, int(0.125 * H), int(0.62 * W), int(0.746 * H)]
    # THE RULES WERE SET ON A ZOOMED FRAME, where a row is sixty rows deep
    # and a word's margin fourteen columns; a window under 1600 columns
    # wide is read at twice its size so the same rules hold, and every
    # measure is halved again on the way out
    up = 2 if (wb[2] - wb[0]) < 1600 else 1
    if up == 2:
        im2 = Image.fromarray(rgb).resize((W * 2, H * 2), Image.LANCZOS)
        rgb = np.asarray(im2)
        g = np.asarray(im2.convert("L"), dtype=np.float32)
        wb = [v * 2 for v in wb]
        H, W = g.shape
    x0, y0, x1, y1 = wb
    # a box that is the list pane itself has no sidebar inside it
    xl = x0 if list_box else divider(g, wb)
    hdr_top, hdr_bot, cols = find_header(rgb, xl, x1, wb)
    if hdr_bot is None:
        hdr_top, hdr_bot = y0 + int(0.1 * (y1 - y0)), y0 + int(0.14 * (y1 - y0))
    border = bottom_border(g, wb, xl)
    list_top = hdr_bot + 4
    bands_ = ink_bands(rgb, xl, x1, list_top, border - 4)
    centers = [(a + b) / 2.0 for a, b in bands_]
    gaps = np.diff(centers)
    band_h0 = int(np.median([b - a for a, b in bands_])) if bands_ else 20
    # the pitch is the commonest gap between rows of writing; with fewer
    # than three rows in view, or gaps that disagree (a black band across
    # a mid-scroll frame), a row is about twice the height of its writing
    med_gap = float(np.median(gaps)) if len(gaps) else 0.0
    agree = [g_ for g_ in gaps if abs(g_ - med_gap) <= 0.2 * med_gap] if len(gaps) else []
    if len(gaps) >= 2 and len(agree) >= 0.6 * len(gaps):
        pitch = int(med_gap)
    else:
        pitch = int(2.1 * band_h0)
    # the pathbar is one row's height above the bottom border; the list ends above it
    # the line found is the pathbar's own top when rows of the box lie
    # below it; the window's bottom border otherwise, with the pathbar above
    if border >= y1 + 2:
        path_top = y1
    elif (y1 - border) > 0.6 * pitch:
        path_top = border
    else:
        path_top = border - int(1.1 * pitch)
    list_bot = path_top - 2
    bands_ = [(a, b) for a, b in bands_ if a < list_bot - 4]
    band_h = int(np.median([b - a for a, b in bands_])) if bands_ else pitch // 2
    name_left = cols[0][0] if cols else xl + 60
    ic0, ic1 = max(xl, name_left - int(0.9 * pitch)), name_left - 4
    col_lefts = ([c[0] for c in cols] or [name_left]) + [x1]
    out_rows = []
    for (a, b) in bands_:
        cy = (a + b) / 2.0
        ry0, ry1 = int(cy - pitch / 2.0), int(cy + pitch / 2.0)
        cut = (a - list_top <= 12) or (list_bot - b <= 12) or ((b - a) < 0.75 * band_h)
        # a black band across a mid-scroll frame touching the row's writing
        # took part of it: the rows just above and below the writing, dark
        # across the width
        for yy in (max(list_top, a - 4), min(list_bot - 1, b + 3)):
            if (g[yy, xl + 40:x1 - 60] < 12).mean() > 0.9:
                cut = True
        sel_c = rgb[max(a, ry0):min(b, ry1), xl + 200:x1 - 80].astype(np.float32)
        sel = bool(((sel_c[:, :, 1] - np.maximum(sel_c[:, :, 0], sel_c[:, :, 2])) > 25).mean() > 0.4) if sel_c.size else False
        icon, n = icon_of(rgb, max(list_top, ry0), min(list_bot, ry1), ic0, ic1)
        # one reading per cell, each cell cropped to its column and read on
        # its own, so the engine never runs the row's words together
        cells, scores, blanks = [], [], 0
        ya, yb = max(list_top, ry0), min(list_bot, ry1)
        for k in range(max(1, len(col_lefts) - 1)):
            ca, cb = (col_lefts[k] - 6 if k < len(col_lefts) else name_left - 6), (col_lefts[k + 1] - 10 if k + 1 < len(col_lefts) else x1 - 60)
            if k == len(col_lefts) - 2:
                cb = x1 - 60
            if cb - ca < 30 or yb - ya < 8:
                cells.append(""); continue
            txt, sc, blank = read_cell(rgb, ya, yb, ca, cb, twice=(k == 0))
            cells.append(txt); scores.append(sc); blanks += blank
        conf = float(np.mean([s for s in scores if s > 0])) if any(s > 0 for s in scores) else 0.0
        if conf < 0.7:
            cut = True                     # read too poorly to stand: a row the edge or the pointer spoiled
        out_rows.append({"y": [int(ry0), int(ry1)], "ink": [int(a), int(b)], "selected": sel, "cut": bool(cut), "icon": icon,
                         "cells": cells, "conf": round(conf, 3), "blank": blanks})
    d_ = float(up)
    thumb = shapes.scroll_thumb(path, [v / d_ for v in (name_left, hdr_bot, x1, path_top)])
    side = shapes.scroll_thumb(path, [v / d_ for v in (max(0, xl - 400), y0, xl - 6, y1)], reach=min(400, max(40, xl - 6)) / d_)
    for r in out_rows:
        r["y"] = [int(v / d_) for v in r["y"]]; r["ink"] = [int(v / d_) for v in r["ink"]]
    rec = {"frame": os.path.basename(path), "window": [int(v / d_) for v in wb], "divider": int(xl / d_),
           "header": [int(hdr_top / d_), int(hdr_bot / d_)], "path_top": int(path_top / d_), "up": up,
           "pitch": int(pitch / d_), "columns": [(int(c[0] / d_), c[1]) for c in cols], "rows": out_rows, "thumb": thumb, "side_thumb": side}
    if not out_dir:
        return rec
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    with open(os.path.join(out_dir, stem + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    if up == 2:      # the overlay is drawn on the enlarged frame, in its own coordinates
        cols = [(c[0] * 2, c[1]) for c in rec["columns"]]; hdr_top, hdr_bot, path_top = hdr_top, hdr_bot, path_top
    im = Image.fromarray(rgb).crop((x0, y0, x1, y1)); d = ImageDraw.Draw(im)
    d.rectangle((xl - x0, 0, xl - x0 + 2, y1 - y0), fill=(255, 0, 255))
    d.line((0, hdr_bot - y0, x1 - x0, hdr_bot - y0), fill=(0, 200, 255), width=2)
    d.line((0, hdr_top - y0, x1 - x0, hdr_top - y0), fill=(0, 120, 255), width=1)
    d.line((0, path_top - y0, x1 - x0, path_top - y0), fill=(0, 200, 255), width=2)
    for cl, t_ in cols:
        d.line((cl - x0, hdr_top - y0, cl - x0, path_top - y0), fill=(255, 200, 0), width=1)
    for r in out_rows:
        col = (255, 80, 80) if r["cut"] else ((80, 255, 80) if r["selected"] else (80, 160, 255))
        ry0_, ry1_ = r["y"][0] * up, r["y"][1] * up
        d.rectangle((name_left - 6 - x0, ry0_ - y0, x1 - 8 - x0, ry1_ - y0), outline=col, width=2)
        d.text((name_left - x0 + 4, ry0_ - y0 + 2), ("%s | " % r["icon"]) + " | ".join(r["cells"])[:110], fill=(255, 255, 0))
    s = 1400 / im.width
    im.resize((1400, int(im.height * s))).save(os.path.join(out_dir, stem + "-overlay.png"))
    return rec

if __name__ == "__main__":
    path, out = sys.argv[1], sys.argv[2]
    hint = sys.argv[3] if len(sys.argv) > 3 else "memory"
    rec = read_frame(path, out, hint)
    print("window", rec["window"], "divider", rec["divider"], "header", rec["header"], "path_top", rec["path_top"], "pitch", rec["pitch"])
    print("columns", rec["columns"])
    print("thumb", rec["thumb"], "side", rec["side_thumb"])
    for r in rec["rows"]:
        print(("CUT " if r["cut"] else "    ") + ("SEL " if r["selected"] else "    ") + r["icon"].ljust(6), r["y"], "%.2f" % r["conf"], " | ".join(r["cells"]))
