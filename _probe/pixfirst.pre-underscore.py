"""Pixels first, words second: one Finder list window read from its picture.

The structure comes from the pixels alone -- the window's rectangle, the
sidebar's dividing line, the toolbar and header bands, the rows from the
list's own stripes, the selected band from its colour, the icons from
their colour, the columns from the header's words, the thumb from its
bar -- and only then are the words read, row by row, into that structure.
Run under the Windows venv (cv2, rapidocr):
    python _probe/pixfirst.py <frame.png> <out_dir> [<title>]
"""
import json, os, re, sys, time
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

def leading_dot(rgb, ya, yb, ca, cb):
    """A hidden file's leading dot, read off the pixels: the first run of
    ink in the name's band is a small blob, no wider than two fifths of
    the writing's height and no taller than that, sitting low on the
    line, with a gap before the letters. The engines read that dot as a
    letter (".local" as "Jocal", ".claude" as "aclaude") or drop it, so
    the dot is cut away before reading and put back after. Returns (the
    dot's last column, the letters' first column) in frame pixels, or
    None where there is no such dot."""
    band = rgb[ya:yb, ca:cb]
    if band.size == 0:
        return None
    ink = ink_mask(band)
    cols = ink.sum(axis=0)
    runs, start = [], None
    for i, v in enumerate(cols):
        if v > 0 and start is None:
            start = i
        elif v == 0 and start is not None:
            runs.append((start, i)); start = None
    if start is not None:
        runs.append((start, len(cols)))
    runs = [(a, b) for a, b in runs if b - a >= 2]
    if not runs:
        return None
    a, b = runs[0]
    trows = np.where(ink.any(axis=1))[0]
    if trows.size == 0:
        return None
    h = trows[-1] - trows[0] + 1
    # a dot joined to the letter after it (a j's hook curls back under it on
    # a doubled frame): the run opens with a shoulder of low, short columns
    # before the first tall one
    k = 0
    for j in range(a, b):
        lit = np.where(ink[:, j])[0]
        if lit.size and lit.size <= 0.4 * h and lit[0] >= trows[0] + 0.55 * h:
            k += 1
        else:
            break
    if 2 <= k <= 0.45 * h and a + k < b:
        return ca + a + k, ca + a + k
    if len(runs) < 2:
        return None
    rows = np.where(ink[:, a:b].any(axis=1))[0]
    if rows.size == 0:
        return None
    if (b - a) > 0.45 * h or (rows[-1] - rows[0] + 1) > 0.4 * h:
        return None                          # a letter, not a dot
    if rows[-1] < trows[0] + 0.55 * h:
        return None                          # sits high: an apostrophe, a dash
    gap = runs[1][0] - b
    if gap < 1 or gap > 0.8 * h:
        return None
    return ca + b, ca + runs[1][0]

def _remark(txt, o, marks="._-"):
    """The other reading's marks (dots, underscores, dashes) set into txt
    where its letters agree with txt's: never a letter, never a colon."""
    import difflib
    out = ""
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, txt, o).get_opcodes():
        if tag == "equal" or tag == "delete":
            out += txt[i1:i2]
        elif tag == "insert":
            ins = o[j1:j2]
            out += ins if ins and all(c in marks for c in ins) else ""
        else:
            a_, b_ = txt[i1:i2], o[j1:j2]
            if not a_.strip() and b_ and all(c in marks for c in b_):
                out += b_                    # a space where the other reading has a dot: the dot's own gap
                continue
            lead = b_[:len(b_) - len(b_.lstrip(marks))]; trail = b_[len(b_.rstrip(marks)):]
            out += (lead + a_ + trail) if b_.strip(marks).lower() == a_.lower() else a_
    return out

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
        s = sum(_ratio(f, g_) for j, g_ in enumerate(folds) if j != i and g_) + 0.002 * len(f)
        if s > best_s:
            best_i, best_s = i, s
    return best_i

def _respace(txt, alt):
    """txt's letters with alt's spaces, where the two hold the same letters."""
    ft, fa = _FOLD(txt), _FOLD(alt)
    if len(ft) != len(fa) or alt.count(" ") <= txt.count(" "):
        return txt
    txt = txt.replace(" ", "")
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
_LOOK = {("o", "0"), ("l", "1"), ("i", "1"), ("s", "5"), ("b", "8"), ("z", "2"), ("g", "9"), ("q", "9")}

def _lookalike(txt, alt):
    """txt with a letter swapped for the digit alt read there (or a digit
    for alt's letter) where the two are look-alikes and alt's run of
    characters is of one class (all digits, all letters) while txt's is
    mixed: "0o" beside "00" is a doubled zero, "O6" beside "06" a six."""
    import difflib
    def fold_map(s):
        pos, f = [], ""
        for i, ch in enumerate(s):
            if re.match(r"[A-Za-z0-9]", ch):
                pos.append(i); f += ch.lower()
        return pos, f
    pt, ft = fold_map(txt); pa, fa = fold_map(alt)
    if not ft or not fa:
        return txt
    def run_class(s, i):
        # the token (letters and digits unbroken by a space or a mark)
        # round index i of the original string, as one class or mixed
        a = i
        while a > 0 and s[a - 1].isalnum():
            a -= 1
        b = i
        while b + 1 < len(s) and s[b + 1].isalnum():
            b += 1
        seg = s[a:b + 1]
        if seg.isdigit():
            return "digit"
        if seg.isalpha():
            return "alpha"
        return "mixed"
    out = list(txt)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ft, fa).get_opcodes():
        if tag != "replace" or (i2 - i1) != (j2 - j1):
            continue
        for k in range(i2 - i1):
            a_, b_ = ft[i1 + k], fa[j1 + k]
            if (a_, b_) in _LOOK or (b_, a_) in _LOOK:
                if run_class(txt, pt[i1 + k]) == "mixed" and run_class(alt, pa[j1 + k]) != "mixed":
                    out[pt[i1 + k]] = alt[pa[j1 + k]]
    return "".join(out)

def _undouble(txt, alt):
    """txt with a letter struck out wherever it doubles a letter that alt,
    agreeing on everything else, has once: the first engine doubles a
    letter now and then at a large size ("PPersonal", "20266")."""
    import difflib
    pos, ft = [], ""
    for i, ch in enumerate(txt):
        if re.match(r"[A-Za-z0-9]", ch):
            pos.append(i); ft += ch.lower()
    fa = _FOLD(alt)
    if not ft or not fa or len(ft) <= len(fa):
        return txt
    drop = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ft, fa).get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete" and i2 - i1 == 1 and ((i1 > 0 and ft[i1] == ft[i1 - 1]) or (i2 < len(ft) and ft[i1] == ft[i2])):
            drop.append(pos[i1]); continue
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            continue                       # a letter read differently is no reason to strike one
        return txt
    if not drop:
        return txt
    return "".join(ch for i, ch in enumerate(txt) if i not in set(drop))

def _rapid_text(crop, scale, height):
    got = ocr(crop, scale)
    return _join(got, height), [w[5] for w in got]

def win_words(rgb, xl, x1, y0, y1):
    """The third reader's words over the list area, once per frame, in the
    frame's own pixels: [(x0, y0, x1, y1, text)]. Windows' own OCR reads
    the pane at its working size; enlarging it further makes it worse.
    None when the reader is not on this machine or is switched off."""
    if os.environ.get("PF_WIN", "3") == "0":
        return None
    try:
        import winocr
        if not winocr.available():
            return None
        got = winocr.read_words(rgb[y0:y1, xl:x1], scale=1.0)
    except Exception as e:
        if os.environ.get("PF_DEBUG"):
            print("   winocr off:", e)
        return None
    return [(a + xl, b + y0, c + xl, d + y0, t) for a, b, c, d, t in got]

def list_words(rgb, xl, x1, y0, y1, scale=2.0):
    """THE FIRST ENGINE OVER THE WHOLE LIST, ONCE -- the same shape win_words
    already used for the third engine, and the reason a pane can cost twenty
    seconds instead of a hundred.

    Measured, and it is the whole speed story of this file: reading a pane
    cell by cell spends 93 to 96 per cent of its time in those calls (75.6s
    total against 70.2s in cells; 113.9 against 109.5; 103.4 against 99.3),
    while the structure the pixels give -- rows, columns, edges -- costs four
    to five seconds. The order was never the problem. "Words second" had
    quietly become "words, one cell at a time, dozens of times a pane".

    So the words are read once over the list area and placed into the cells
    they fall in. A cell the placement leaves empty, or whose text fails the
    shape its column expects, is still read on its own -- that is where the
    accuracy of cell-by-cell reading is actually earned, and it is a handful
    of cells rather than all of them.

    Returns [(x0, y0, x1, y1, text, score)] in the FRAME's own pixels."""
    crop = rgb[y0:y1, xl:x1]
    if crop.size == 0:
        return []
    got = ocr(crop, scale)
    out = []
    for a, b, c, d, t, sc in got:
        out.append((a / scale + xl, b / scale + y0, c / scale + xl, d / scale + y0, t, sc))
    return out


def cell_from(words, ya, yb, ca, cb, height):
    """One cell's text and mean score from a whole-list reading: the words
    whose centre lies inside it, in reading order. Mirrors win_cell, which
    has done exactly this for the third engine since it was added."""
    got = [w for w in words if ca <= (w[0] + w[2]) / 2.0 <= cb and ya <= (w[1] + w[3]) / 2.0 <= yb]
    if not got:
        return "", 0.0
    return _join([(w[0], w[1], w[2], w[3], w[4]) for w in got], height), float(np.mean([w[5] for w in got]))


def win_cell(words, ya, yb, ca, cb, height):
    """The third reader's text inside one cell: its words whose centre lies
    in the cell, in reading order, a space at a gap a third of the height."""
    if not words:
        return ""
    got = [w for w in words if ca <= (w[0] + w[2]) / 2.0 <= cb and ya <= (w[1] + w[3]) / 2.0 <= yb]
    return _join(got, height)

def _vote(rapid_reads, alt, win):
    """One vote per engine. The first engine's own pick is whichever of its
    reads is most like the other engines' (its sharper read when there is
    nothing to compare); then the reading most like the others stands.
    Returns (text, index of the standing engine: 0 first, 1 second, 2 third, or None)."""
    others = [o for o in (alt, win) if o]
    rr = [r for r in rapid_reads if r]
    if rr and others:
        rapid = max(rr, key=lambda r: sum(_ratio(_FOLD(r), _FOLD(o)) for o in others) + 0.001 * len(r))
    else:
        rapid = rr[0] if rr else ""
    cands = [rapid, alt or "", win or ""]
    # WHY THE MARKS ARE SETTLED SEPARATELY BELOW.
    #
    # The medoid compares FOLDED readings -- letters and digits only. When the
    # engines agree on a name's letters and differ only in its marks, every
    # fold is identical, every similarity score ties, and the tie falls to the
    # first candidate, which is always the first engine. That engine is the one
    # with the underscore fault, so the tie is decided in favour of the reading
    # known to be wrong about marks, every time.
    #
    # Measured on the memory pane at 00:01:20, sixteen names against the true
    # ones. `reference_utm_convention.md` was read correctly by BOTH the second
    # and third engines and still came out `reference.utm.convention.md`.
    #
    # Two blunter rules were tried and are recorded here so they are not tried
    # again. Taking the third engine's whole reading: 14 of 16 on this pane but
    # 29 of 43 on the test panes, because that engine has its own faults there
    # (`.locai`, `.cloudf:ared`) and writes an em-dash for an underscore. A
    # count of marks (_MARKS) to detect the disagreement: never fires, because
    # `reference_utm_convention.md` and `reference.utm.convention.md` both
    # count three. The rule that stands is below: letters by majority, marks
    # from the second engine when it read the very same letters.
    mode = os.environ.get("PF_NAME", "marks")   # "medoid" puts back the old behaviour
    if mode == "win" and (win or "").strip():
        return win, 2                    # measured WORSE (29 of 43); kept only to re-measure
    i = _medoid(cands)
    txt = cands[i] if i is not None else ""
    # PF_NAME=marks -- the narrow fix, and the one the measurement supports.
    # Keep the majority's LETTERS (the medoid is right 41 of 43 on the test
    # panes) and take the SECOND engine's MARKS where it read the very same
    # letters. Underscore against dot is invisible to the vote, because the
    # comparison folds a reading to letters and digits alone; the two spellings
    # are one candidate to it and the marks then fall to whichever engine
    # happened to win, which is the pair that shares the underscore weakness.
    # This can never change a letter: it fires only when the second engine's
    # reading folds identically to the standing one.
    if mode != "medoid" and txt:
        # The marks come from the engine measured best on marks, which is the
        # SECOND engine (alt), not the third: on the memory pane the third
        # engine writes an em-dash where the name has an underscore
        # (`user--review--drafts...`), and taking its marks scored 1 of 16.
        # Folds equal and the strings differ => the whole difference is marks
        # and spacing, so the second engine's spelling stands. _MARKS is not
        # used here: it counts marks without telling their kind, and
        # `reference_utm_convention.md` and `reference.utm.convention.md` both
        # count three, so a count test never fires on the very case this is for.
        if alt and alt != txt and _FOLD(alt) == _FOLD(txt):
            return alt, 1
    return txt, i


def _cell_crop(rgb, ya, yb, ca, cb, twice):
    """The crop a cell is read from: its ink, cut at the column's own left
    at the earliest, padded forty columns each side and eight rows above
    and below with the crop's own median colour. Returns (crop, the word
    boxes, the leading dot, the row's height, the crop's top and bottom),
    or None where the cell holds no ink. Built in ONE place so the batch
    reader and the cell reader read exactly the same pixels."""
    H = rgb.shape[0]
    boxes = word_crops(rgb, ya, yb, ca, cb)
    if not boxes:
        return None
    y0_, y1_ = max(0, ya - 6), min(H, yb + 6)
    height = max(8, yb - ya)
    # a hidden file's leading dot is left out of the crop and put back after
    dot = leading_dot(rgb, ya, yb, ca, cb) if twice else None
    if dot:
        x0_ = max(ca + 6, dot[1] - min(6, max(1, (dot[1] - dot[0]) // 2)))
    else:
        x0_ = max(ca + 6, boxes[0][0] - 6)
    x1_ = min(cb, boxes[-1][1] + 6)
    crop = rgb[y0_:y1_, x0_:x1_]
    # the engine's detector drops a first word or reads two letters of seven
    # from a crop cut close, and the second engine reads a streaked pad as
    # "=" and "m"; one flat colour, the crop's own (a green band pads green)
    bg = np.median(crop.reshape(-1, 3), axis=0).astype(crop.dtype)
    h_, w_ = crop.shape[:2]
    padded = np.empty((h_ + 16, w_ + 80, 3), dtype=crop.dtype)
    padded[:, :] = bg
    padded[8:8 + h_, 40:40 + w_] = crop
    return padded, boxes, dot, height, y0_, y1_


# THE COST OF READING A CELL IS THE CALL, NOT THE PIXELS.
#
# Measured: one engine call on a cell-sized crop costs about 0.6 s whatever
# the crop's size -- upscaling it three times (nine times the pixels) costs
# the same 0.6 s, and not upscaling it at all saves nothing. The engine's
# detector resizes its input to a fixed size before it looks at anything, so
# every call pays the same toll. Sixty-four cells therefore cost sixty-four
# tolls, and a pane spent forty seconds paying them.
#
# So the saving is fewer calls, not smaller ones: every cell of a pane is
# laid out down ONE tall canvas with a gap between, and the engine reads the
# lot in a single call. Each reading comes back with its y, which says whose
# it is -- the gap is what keeps the engine from running two cells together.
# Measured on the seventeen-row pane: 41.4 s in sixty-eight calls became
# 4.6 s in one. A cell the canvas yields nothing for still goes to the cell
# reader on its own, so the hard cells keep the careful pass.
_BATCH = {}
_BATCH_GAP = 24


# THE SAME PIXELS CANNOT SAY TWO THINGS.
#
# The batch above spares a PANE its repeated calls, and is thrown away when
# the next frame opens. But a video shows one folder over and over: the same
# window, the same rows, at ten moments. Measured across the whole video --
# 1,662 cells read from 42 panes -- only 831 crops are distinct BYTE FOR
# BYTE. Half of every read was the same picture handed to the same engine
# for the same answer.
#
# So a cell's crop is fingerprinted by its bytes and its reading kept for
# the length of the run. An identical crop takes the remembered reading and
# calls no engine at all. This cannot be wrong in the way a clever key can:
# the same bytes through the same code give the same answer, and the check
# that says so counted zero disagreements over all 1,662 cells.
#
# A LOOSER KEY IS NOT WORTH IT, MEASURED. The same crops shrunk to sixteen
# rows, greyed and quantised -- a fingerprint that ought to forgive a pixel
# of anti-aliasing -- found 816 distinct against exact bytes' 831: one point
# of saving for a key that CAN be wrong. Exact bytes it is.
_SEEN = {}          # crop fingerprint -> the batch's reading of it
_SEEN_ALT = {}      # crop fingerprint -> the second engine's word boxes
_SEEN_CELL = {}     # (crop fingerprint, name?, the third reader's word) -> the finished reading
_SEEN_HITS = [0, 0, 0, 0]     # batch hits, batch asks, cell hits, cell asks


def _fingerprint(crop):
    import hashlib
    return hashlib.sha1(np.ascontiguousarray(crop).tobytes()).digest()


def memory_report():
    """hits and asks, for a run that wants to print what the memory saved."""
    b_h, b_a, c_h, c_a = _SEEN_HITS
    return ("cell memory: %d of %d whole cells and %d of %d batch crops were "
            "pictures already read" % (c_h, c_a, b_h, b_a))


def _tess_prep(rgb_crop):
    """A crop as the second engine wants it: the darkest channel, enlarged,
    dark writing on light paper. The same preparation tess_word makes, kept
    apart so a canvas of many crops can be built from it."""
    im = Image.fromarray(rgb_crop.min(axis=2).astype(np.uint8))
    k = max(2, 4 // _UP[0])
    im = im.resize((im.width * k, im.height * k), Image.LANCZOS)
    g = np.asarray(im)
    return (255 - g) if float(np.median(g)) < 128 else g

def _tess_tsv(gray, psm=6):
    """Every line the second engine finds in an image, with its top and
    bottom: [(top, bottom, text)]. Plain stdout gives the words but not
    where they sat, and where they sat is what says whose they are."""
    import subprocess, tempfile, os as _os, cv2, machine
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        path = fh.name
    try:
        cv2.imwrite(path, gray)
        r = subprocess.run([machine.tesseract_or_refuse(), path, "stdout", "-l", "eng",
                            "--psm", str(psm), "tsv"],
                           capture_output=True, text=True, encoding="utf-8")
        rows = {}
        for ln in (r.stdout or "").splitlines()[1:]:
            f = ln.split("\t")
            if len(f) < 12 or not f[11].strip():
                continue
            try:
                top, h = int(f[7]), int(f[9])
            except ValueError:
                continue
            key = (f[2], f[3], f[4])          # block, paragraph, line
            a, b, w = rows.get(key, (top, top + h, []))
            rows[key] = (min(a, top), max(b, top + h), w + [f[11]])
        return [(a, b, " ".join(w)) for (a, b, w) in rows.values()]
    except Exception:
        return []
    finally:
        try: _os.unlink(path)
        except Exception: pass

_BATCH_ALT = {}

def batch_tess(keys, crops, gap):
    """The second engine over every cell of a pane in ONE call. It spawns a
    process and writes a file per call, which is the whole of its cost: 64
    cells cost 11.6 s in 64 calls and about a second in one."""
    if not crops:
        return
    prepped = [_tess_prep(c) for c in crops]
    G = gap * max(2, 4 // _UP[0])
    W = max(p.shape[1] for p in prepped) + 40
    H = sum(p.shape[0] for p in prepped) + G * (len(prepped) + 1)
    canvas = np.full((H, W), 255, dtype=np.uint8)
    at = []; y = G
    for p in prepped:
        canvas[y:y + p.shape[0], 20:20 + p.shape[1]] = p
        at.append((y, y + p.shape[0])); y += p.shape[0] + G
    got = _tess_tsv(canvas, psm=6)
    per = ["" for _ in crops]
    for (a, b, txt) in got:
        yc = (a + b) / 2.0
        for n, (a_, z_) in enumerate(at):
            if a_ - G / 2.0 <= yc <= z_ + G / 2.0:
                per[n] = (per[n] + " " + txt).strip(); break
    for n, k in enumerate(keys):
        _BATCH_ALT[k] = per[n]

def batch_key(ya, yb, ca, cb, twice):
    return (int(ya), int(yb), int(ca), int(cb), bool(twice))

def batch_read(rgb, specs, scale=None):
    """Read every cell in `specs` -- (ya, yb, ca, cb, twice) -- in as few
    engine calls as the canvas cap allows, and leave each reading in _BATCH
    under its own key."""
    if os.environ.get("PF_BATCH", "1") != "1":
        return
    scale = float(os.environ.get("PF_BATCH_SCALE", "1.0")) if scale is None else scale
    cap = int(os.environ.get("PF_BATCH_CAP", "6000000"))
    made = []
    mem = os.environ.get("PF_MEMORY", "1") == "1"
    for sp in specs:
        k = batch_key(*sp)
        if k in _BATCH:
            continue
        c = _cell_crop(rgb, sp[0], sp[1], sp[2], sp[3], sp[4])
        if c is None:
            _BATCH[k] = ("", [])
            continue
        fp = _fingerprint(c[0]) if mem else None
        _SEEN_HITS[1] += 1
        if fp is not None and fp in _SEEN:
            _BATCH[k] = _SEEN[fp]
            if fp in _SEEN_ALT:
                _BATCH_ALT[k] = _SEEN_ALT[fp]
            _SEEN_HITS[0] += 1
            continue
        made.append((k, c[0], c[3], fp))
    i = 0
    while i < len(made):
        # as many crops as fit the cap, then one call
        W = 0; H = _BATCH_GAP; j = i
        while j < len(made):
            w_ = max(W, made[j][1].shape[1] + 40)
            h_ = H + made[j][1].shape[0] + _BATCH_GAP
            if j > i and w_ * h_ * scale * scale > cap:
                break
            W, H = w_, h_; j += 1
        crops = [m[1] for m in made[i:j]]
        bg = np.median(np.concatenate([c.reshape(-1, 3) for c in crops]), axis=0).astype(rgb.dtype)
        canvas = np.empty((H, W, 3), dtype=rgb.dtype); canvas[:, :] = bg
        at = []; y = _BATCH_GAP
        for c in crops:
            canvas[y:y + c.shape[0], 20:20 + c.shape[1]] = c
            at.append((y, y + c.shape[0])); y += c.shape[0] + _BATCH_GAP
        try:
            got = ocr(canvas, scale)
        except Exception:
            got = []
        per = [[] for _ in crops]
        for b in got:
            yc = (b[1] + b[3]) / 2.0
            for n, (a_, z_) in enumerate(at):
                if a_ - _BATCH_GAP / 2.0 <= yc <= z_ + _BATCH_GAP / 2.0:
                    # back into the crop's own pixels, so _join sees what it expects
                    per[n].append((b[0] - 20, b[1] - a_, b[2] - 20, b[3] - a_, b[4], b[5]))
                    break
        for n, (k, _c, hgt, fp) in enumerate(made[i:j]):
            _BATCH[k] = (_join(per[n], hgt), [w[5] for w in per[n]])
            if fp is not None:
                _SEEN[fp] = _BATCH[k]
        # THE SECOND ENGINE IS NOT BATCHED, MEASURED. The same canvas trick
        # works on it -- one process instead of sixty-eight -- and on a pane
        # read alone it cut 23.7 s to 16.5 s. On the three-pane test it LOST:
        # reading a tall canvas as one block (psm 6) rather than each cell as
        # one line (psm 7) reads well enough to stand but not well enough to
        # agree, so nearly every cell failed the doubt test and bought a
        # careful pass by the dearer engine. Kept, off, for the day the
        # canvas is laid out so the block reading holds. PF_BATCH_TESS=1.
        if os.environ.get("PF_BATCH_TESS", "0") == "1":
            try:
                batch_tess([m[0] for m in made[i:j]], crops, _BATCH_GAP)
            except Exception:
                pass
            for k, _c, _h, fp in made[i:j]:
                if fp is not None and k in _BATCH_ALT:
                    _SEEN_ALT[fp] = _BATCH_ALT[k]
        i = j

def read_cell(rgb, ya, yb, ca, cb, twice=False, win=""):
    """The finished reading of a cell, from the memory where this exact
    picture has been read before and from the engines where it has not.

    The memory is keyed on the crop's own bytes together with the two things
    outside the crop that change the answer: whether the cell is a name, and
    the third reader's word for the same place. Everything else the vote
    uses comes out of the crop itself, so the same key can only stand for
    the same reading."""
    if os.environ.get("PF_MEMORY", "1") != "1":
        return _read_cell_once(rgb, ya, yb, ca, cb, twice, win)
    got_ = _cell_crop(rgb, ya, yb, ca, cb, twice)
    if got_ is None:
        return "", 0.0, 0
    key = (_fingerprint(got_[0]), bool(twice),
           re.sub(r"\s+", " ", win or "").strip())
    _SEEN_HITS[3] += 1
    if key in _SEEN_CELL:
        _SEEN_HITS[2] += 1
        return _SEEN_CELL[key]
    # the crop is handed on rather than cut a second time: cutting it means
    # finding the row's words in the ink, and it has just been done
    out = _read_cell_once(rgb, ya, yb, ca, cb, twice, win, got_)
    _SEEN_CELL[key] = out
    return out


def _read_cell_once(rgb, ya, yb, ca, cb, twice=False, win="", got_=None):
    """A cell's text by majority. A name (twice=True) is one crop over the
    whole of its ink, read by the first engine at two sizes and by the
    second engine once; the reading most like the other two stands, with
    the second engine's underscores and spaces laid over it where its
    letters agree. Any other cell is read whole at two sizes, word by word
    (each word cropped with its own margin, padded with background), and by
    the second engine; the reading most like the others stands, and a date
    or a size then takes the shape Finder writes it in. Returns (text, mean
    confidence, the count of words the engine could not read)."""
    if got_ is None:
        got_ = _cell_crop(rgb, ya, yb, ca, cb, twice)
    if got_ is None:
        return "", 0.0, 0
    whole_crop, boxes, dot, height, y0_, y1_ = got_
    _sc = float(os.environ.get("PF_SCALE", "3.0"))
    win = re.sub(r"\s+", " ", win or "").strip()
    # The second engine is woken FIRST here. It is read either way, so
    # reading it first costs nothing -- and it is what says whether the
    # batch's reading of this cell can stand.
    _bk = batch_key(ya, yb, ca, cb, twice)
    _ba = _BATCH_ALT.get(_bk)
    alt = re.sub(r"\s+", " ", (_ba if _ba else tess_word(whole_crop))).strip()
    _bb = _BATCH.get(_bk)
    if _ba and _bb and _bb[0] and _ratio(_FOLD(_ba), _FOLD(_bb[0])) < 0.85:
        # THE CHEAPER ENGINE SETTLES ITS OWN DOUBT. Where the two batched
        # readings of a cell disagree, one of them is wrong and the cell
        # needs a careful pass -- but the second engine's careful pass costs
        # a fifth of the first engine's, so it is asked first. It agrees
        # with the batch often enough to save the dearer call outright.
        alt = re.sub(r"\s+", " ", tess_word(whole_crop)).strip()
    _b = _bb
    r3, s3 = None, None
    if _b is not None and _b[0]:
        # THE BATCH'S READING STANDS ONLY WHERE ANOTHER ENGINE BACKS IT.
        # Reading a whole pane in one call is nine times cheaper than reading
        # its cells one at a time, and on all but a handful it reads the same.
        # The handful is the point: where the batch's reading is backed by
        # NEITHER other engine, the cell is read again on its own, the careful
        # way. Doubt is measured on letters and digits alone, so a
        # disagreement about underscores never buys a pass it cannot settle.
        if any(o and _ratio(_FOLD(_b[0]), _FOLD(o)) >= 0.85 for o in (alt, win)):
            r3, s3 = _b
        # A CELL'S SHAPE IS NOT ITS CORRECTNESS, MEASURED. It was tried:
        # let a batched reading stand unbacked where finder_shape already
        # recognises it, on the reasoning that a date that reads as a date
        # is a finished reading. The test read "Today at 7:66 PM" for
        # "Today at 7:55 PM" -- a flawless date shape with a wrong digit --
        # and the score fell from 41 of 43 rows to 40. A shape test cannot
        # see a misread digit, and a misread digit is what the second engine
        # is there to catch. Only another engine's agreement will do.
    if r3 is None:
        r3, s3 = _rapid_text(whole_crop, _sc, height)
    # THE SECOND SIZE IS OFF, MEASURED. Every cell used to be read by the
    # first engine at two sizes, on the reasoning that a size that suits one
    # cell suits another badly. On the three-pane test the second size
    # changed NOTHING: 41 of 43 rows and 169 of 172 cells with it and
    # without, and it cost a third of the reading. PF_SCALE2=1 puts it back.
    if os.environ.get("PF_SCALE2", "0") == "1":
        r2, s2 = _rapid_text(whole_crop, _sc * 2.0 / 3.0, height)
    else:
        r2, s2 = "", []
    # THE SECOND ENGINE IS ALWAYS WOKEN, and here is why it may not be skipped.
    #
    # It was tried: skip it where the first engine's two reads and the third
    # engine already agree, on the reasoning that a fourth opinion cannot
    # change a settled vote. MEASURED WORSE -- the three-pane test fell from
    # 41 of 43 rows to 38, and cells from 169 to 172 down to 166.
    #
    # The premise was wrong in a way worth keeping written down: the agreement
    # test compares readings FOLDED to letters and digits, and the second
    # engine is precisely the one the marks rule takes its punctuation from.
    # Three readings can agree on every letter and differ on every underscore,
    # which is the exact case the marks fix exists for -- so skipping the
    # second engine there removes the fix's own source.
    if twice and dot:
        win = win.lstrip("._")                    # the third reader saw the dot the crop leaves out
    mode = os.environ.get("PF_WIN", "3")
    if twice:
        if mode == "3" and win:
            txt, i = _vote((r3, r2), alt, win)
            scores = (s3 or s2) if i is not None else []
            if not txt or (not r3 and not r2 and len(_FOLD(txt)) < 3):
                return "", 0.0, 1
            i = 3                            # an engine's index below: none of the two first reads by itself
        else:
            cands = [r3, r2, alt] + ([win] if (mode == "4" and win) else [])
            i = _medoid(cands)
            if i is None or (not r3 and not r2 and len(_FOLD(alt)) < 3 and len(_FOLD(win)) < 3):
                return "", 0.0, 1
            txt = cands[i]
            scores = s3 if i == 0 else (s2 if i == 1 else (s3 or s2))
        # the other readings' marks laid over the standing reading where
        # the letters agree: dots, underscores and dashes, never letters;
        # spaces from the second engine
        for o in (alt, win):
            if o and o != txt and _ratio(_FOLD(o), _FOLD(txt)) >= 0.85:
                txt = _remark(_lookalike(_undouble(txt, o), o), o)
                if o is alt:
                    txt = _respace(txt, o)
        txt = re.sub(r"^[^A-Za-z0-9._~$]+", ".", txt)      # a hidden file's leading dot, read as a dash or a comma
        txt = re.sub(r"\. (?=\w)", ".", txt)                # no space beside a dot inside a name
        txt = re.sub(r" \.(?=\w)", ".", txt)
        if dot:
            txt = "." + txt.lstrip("._ ")                      # the dot the pixels showed
        elif not txt.startswith(".") and any(r[:1] == "J" and r[1:2] == "j" for r in (r3, r2)):
            txt = "." + txt.lstrip("._ ")                      # the first engine's "Jj": the dot and the j read as one
        if os.environ.get("PF_DEBUG"):
            print("   name", repr(r3), repr(r2), repr(alt), repr(win), "->", repr(txt))
        return txt, (float(np.mean(scores)) if scores else 0.0), (0 if txt else 1)
    # THE WORD-BY-WORD PASS IS OFF, MEASURED. A non-name cell used to be read
    # a second time one word at a time, each word cropped with its own margin,
    # and the result stood in the vote as a fourth opinion. On the three-pane
    # test it changed NOTHING -- 41 of 43 rows and 169 of 172 cells with it
    # and without -- while costing a hundred and sixty-six engine calls a
    # pane, a third of the reading. It is a fourth voter that never once broke
    # a tie. PF_WORDS=1 puts it back.
    words, scores, blank = [], [], 0
    for i, (wa, wb_) in enumerate(boxes if os.environ.get("PF_WORDS", "0") == "1" else []):
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
    if mode == "3" and win:
        text, i = _vote(tuple(c for c in (r3, r2, pw) if c), alt, win)
        cands = [r3, r2, pw, alt, win]
        if not text:
            return "", 0.0, blank
        scores = s3 or s2 or scores
    else:
        cands = [r3, r2, pw, alt] + ([win] if (mode == "4" and win) else [])
        i = _medoid(cands)
        if i is None:
            return "", 0.0, blank
        text = cands[i]
        scores = ([s3, s2, scores, s3 or s2] + [s3 or s2])[i]
    for o in (alt, win):
        if o and o != text and _ratio(_FOLD(o), _FOLD(text)) >= 0.85:
            text = _remark(_undouble(text, o), o, marks="._-,")     # the other reading's commas and dots, never its letters
    if (boxes[-1][1] - boxes[0][0]) < 1.2 * height and not re.search(r"\d", text):
        text = "--"                          # a folder's size: a dash, read as two letters
    shaped = finder_shape(text)
    if shaped is None:
        for c in cands:
            if c and c is not text and _ratio(_FOLD(c), _FOLD(text)) >= 0.85:
                shaped = finder_shape(c)
                if shaped is not None:
                    break
    # THE KIND IS NOT COMPLETED HERE, AND THE BENCH IS WHY. Spelling a cut
    # "Markdo...text file" whole belongs to the NOTE, not to the reader: the
    # hand-made truth records the truncated form, because what the screen
    # showed is what the reader must return. Completing it here scored 40 of 43
    # rows against 41 -- the one "failure" being the reader no longer saying
    # what was on the glass. The completion lives in draw3, over the record,
    # where legibility is the job and fidelity has already been banked.
    if os.environ.get("PF_DEBUG"):
        print("   cell", [repr(c) for c in cands], "win", repr(win), "->", repr(shaped if shaped is not None else text))
    return (shaped if shaped is not None else text), (float(np.mean(scores)) if scores else 0.0), blank

def finder_shape(s):
    """A date or a size in the shape Finder writes it, from a reading that
    holds the letters and digits but not the spaces: "Jun 30, 2026 at 5:54
    PM", "Today at 8:47 PM", "57 KB". None where the reading is neither."""
    f = re.sub(r"\s+", "", s)
    m = re.fullmatch(r"([A-Za-z]{3})(\d{1,2})[,.]?(\d{4,5})(?:at)?(\d{1,2})[:;.°•](\d{2})(AM|PM)", f)
    if m:
        mon = m.group(1)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        near = max(months, key=lambda x: _ratio(x.lower(), mon.lower()))
        if _ratio(near.lower(), mon.lower()) < 0.66:
            return None
        return "%s %s, %s at %s:%s %s" % (near, m.group(2), m.group(3)[-4:], m.group(4), m.group(5), m.group(6))
    m = re.fullmatch(r"(Today|Yesterday)(?:at)?(\d{1,2})[:;.°•](\d{2})(AM|PM)", f)
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

_PHASE = {}    # read_frame's own split: seconds spent reading cells
_UP = [1]      # the frame's enlargement while it is read (1 or 2), for the second engine's own scale

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
    k = max(2, 4 // _UP[0])                 # four times at one-to-one; two on a frame already doubled
    im = im.resize((im.width * k, im.height * k), Image.LANCZOS)
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
    _BATCH.clear(); _BATCH_ALT.clear()
    # PHASE TIMING. The STRUCTURE (rows, columns and edges taken from the
    # pixels) and the WORDS (every cell handed to the engines) had never been
    # timed apart, so "pixels first costs 70 to 140 seconds a pane" said
    # nothing about which half to fix. SN_PHASE=1 prints the split. The
    # structure is arithmetic on light and dark and ought to be seconds; the
    # words are engine calls and ought to be nearly all of it.
    _PHASE.clear()
    _t_all = time.perf_counter()
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
    _UP[0] = up
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
    words3 = win_words(rgb, xl, x1, list_top, list_bot)      # the third reader, once over the list
    # THE FIRST ENGINE, ALSO ONCE OVER THE WHOLE LIST. Two passes at the two
    # sizes the cell reader used, so nothing it had is lost. PF_ONEPASS=0
    # falls back to reading every cell on its own, as before.
    # ONE READ PER COLUMN, DOWN THE WHOLE LIST -- not one per cell, and not one
    # for the whole list either.
    #
    # Reading the whole list in a single pass was tried and fails outright: the
    # engine groups each ROW into one box, so a name cell came back holding the
    # row's dates and kinds ("Jun30,2026at5:54PM...Folder" where `.obsidian`
    # belonged) and the score fell from 41 of 43 rows to 16. That is exactly
    # what the cell reader's own comment warns of -- each cell is cropped to
    # its column "so the engine never runs the row's words together".
    #
    # A COLUMN STRIP keeps that separation and still collapses the work: four
    # reads a pane instead of one per cell, about sixty. The column is the unit
    # that matters, not the cell -- rows are separated by position afterwards,
    # which costs nothing.
    # OFF BY DEFAULT, AND HERE IS THE MEASUREMENT THAT PUT IT THERE.
    # Reading a whole COLUMN in one pass fails the same way reading a whole ROW
    # does: the engine merges whatever is adjacent to it. A column strip gave
    # `01DailyNotesooInbox` where `.obsidian` belonged -- several rows run
    # together -- and scored 17 of 43 rows against the cell reader's 41. The
    # whole-list pass scored 16 of 43, with a name cell holding the row's dates
    # and kinds. Faster both times (56/99/76s and 41/82/72s against 76/114/104)
    # and useless both times.
    # THE CONCLUSION, which is the opposite of what it looked like: reading
    # cell by cell is NOT redundant work. It is load-bearing, and it is the
    # only unit this engine reads cleanly. The speed must come from somewhere
    # else -- a faster engine (#25), or reading fewer cells, never from reading
    # the same cells in bigger gulps.
    _onepass = os.environ.get("PF_ONEPASS", "0") != "0"
    _strips = {}
    if _onepass:
        for _k in range(max(1, len(col_lefts) - 1)):
            _ca = (col_lefts[_k] - 6 if _k < len(col_lefts) else name_left - 6)
            _cb = (col_lefts[_k + 1] - 10 if _k + 1 < len(col_lefts) else x1 - 60)
            _strips[_k] = (list_words(rgb, max(xl, _ca), min(x1, _cb), list_top, list_bot, 3.0),
                           list_words(rgb, max(xl, _ca), min(x1, _cb), list_top, list_bot, 2.0))
    # EVERY CELL OF THE PANE, READ IN ONE CALL, BEFORE THE ROW LOOP STARTS.
    # The row loop below is unchanged: each cell still asks for its own
    # reading, and finds it already made. A cell the canvas yielded nothing
    # for falls through to its own call, so nothing is lost, only repaid.
    _specs = []
    for (a, b) in bands_:
        cy = (a + b) / 2.0
        _ya, _yb = max(list_top, int(cy - pitch / 2.0)), min(list_bot, int(cy + pitch / 2.0))
        for k in range(max(1, len(col_lefts) - 1)):
            ca_ = (col_lefts[k] - 6 if k < len(col_lefts) else name_left - 6)
            cb_ = (x1 - 60) if k == len(col_lefts) - 2 else (col_lefts[k + 1] - 10 if k + 1 < len(col_lefts) else x1 - 60)
            if cb_ - ca_ >= 30 and _yb - _ya >= 8:
                _specs.append((_ya, _yb, ca_, cb_, k == 0))
    if _specs:
        _tb = time.perf_counter()
        batch_read(rgb, _specs)
        _PHASE["batch"] = _PHASE.get("batch", 0.0) + time.perf_counter() - _tb

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
            _tc = time.perf_counter()
            _win = win_cell(words3, ya, yb, ca, cb, band_h)
            txt = None
            if _onepass:
                # the cell's words out of the two whole-list readings, voted
                # against the third engine exactly as before -- the same
                # decision, made on words already read rather than on a fresh
                # pass per cell
                _s3, _s2 = _strips.get(k, (None, None))
                _a, _sa = cell_from(_s3, ya, yb, ca, cb, band_h)
                _b, _sb = cell_from(_s2, ya, yb, ca, cb, band_h)
                if _a or _b or _win:
                    _t, _i = _vote((_a, _b), "", _win)
                    if _t:
                        _shaped = finder_shape(_t) if k else None
                        _cand = _shaped if _shaped is not None else _t
                        # A CELL IS ONLY TRUSTED FROM THE ONE PASS WHERE IT
                        # LOOKS FINISHED. Empty, or a non-name cell that is
                        # not the shape its column writes (a date that is not
                        # a date, a size that is not a size) goes to the cell
                        # reader, which is where cell-by-cell accuracy is
                        # actually earned -- a handful of cells, not all.
                        if k == 0 or _shaped is not None:
                            txt, sc, blank = _cand, float(np.mean([x for x in (_sa, _sb) if x] or [0.0])), 0
            if txt is None:
                txt, sc, blank = read_cell(rgb, ya, yb, ca, cb, twice=(k == 0), win=_win)
            _PHASE["cells"] = _PHASE.get("cells", 0.0) + time.perf_counter() - _tc
            cells.append(txt); scores.append(sc); blanks += blank
        if icon == "folder" and len(cells) == 4:
            if not re.search(r"\d", cells[2]):
                cells[2] = "--"                # a folder has no size
            if cells[3] and _ratio(cells[3].lower(), "folder") >= 0.66:
                cells[3] = "Folder"
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
    def _phase():
        if os.environ.get("SN_PHASE"):
            _tot = time.perf_counter() - _t_all
            _c = _PHASE.get("cells", 0.0)
            print("   PHASE whole %.1fs | words in cells %.1fs (%.0f%%) | structure and the rest %.1fs"
                  % (_tot, _c, 100.0 * _c / max(_tot, 0.001), _tot - _c), file=sys.stderr)
    _phase()
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
