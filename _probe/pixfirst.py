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
    """The words in a crop, upscaled for the engine: [(x0,y0,x1,y1,text,score)] in the crop's own pixels."""
    im = Image.fromarray(rgb_crop)
    if scale != 1.0:
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    arr = np.asarray(im)[:, :, ::-1].copy()      # BGR for the engine
    res, _ = engine()(arr)
    out = []
    for box, text, score in (res or []):
        xs = [p[0] / scale for p in box]; ys = [p[1] / scale for p in box]
        out.append((min(xs), min(ys), max(xs), max(ys), text, float(score)))
    return out

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
    ink = c.min(axis=2) > 100
    cnt = ink.sum(axis=1).astype(int)
    cnt[cnt > 0.6 * ink.shape[1]] = 0        # a line across the width is a border, not writing
    least = max(least, 12)
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
            ink = (band.min(axis=2) > 90).sum(axis=0)
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
            cols = []
            for s_, e_ in merged:
                got = ocr(rgb[max(0, a - 6):b + 6, max(0, xl + s_ - 10):xl + e_ + 10], 3.0)
                cols.append((xl + s_, " ".join(w[4] for w in sorted(got, key=lambda w: w[0])).strip()))
            return a, b, cols
    return None, None, []

def bottom_border(g, wb, xl):
    """The window's bottom border: a light line across the list's width in
    the window's bottom seventh (or just below the measured box)."""
    x0, y0, x1, y1 = wb
    h = y1 - y0
    xs = slice(xl + 40, x1 - 60)
    bg = float(np.median(g[y0 + h // 3:y0 + 2 * h // 3, xs]))
    for y in range(y1 - int(0.15 * h), min(g.shape[0], y1 + int(0.06 * h))):
        if (g[y, xs] > bg + 20).mean() > 0.9:
            return y
    return y1

def word_crops(rgb, ya, yb, ca, cb, gap=10):
    """A cell's words as separate crops, split at gaps of `gap` columns
    with no ink: [(x0, x1)] in frame pixels."""
    band = rgb[ya:yb, ca:cb]
    ink = (band.min(axis=2) > 100).sum(axis=0)
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

def read_cell(rgb, ya, yb, ca, cb, twice=False):
    """A cell's text, one reading per word, joined with spaces: each word
    cropped with fourteen columns of margin and six rows, read at three
    times its size (four for a word under forty columns). Returns (text,
    the mean confidence, the count of words the engine could not read)."""
    words, scores, blank = [], [], 0
    H = rgb.shape[0]
    for wa, wb_ in word_crops(rgb, ya, yb, ca, cb):
        crop = rgb[max(0, ya - 6):min(H, yb + 6), max(ca, wa - 14):min(cb, wb_ + 14)]
        got = ocr(crop, 3.0 if (wb_ - wa) > 40 else 4.0)
        if twice and (wb_ - wa) > 120:
            # a long word (a file name) reads differently at two sizes; the
            # engine's own confidence picks between them
            got2 = ocr(crop, 2.0)
            if got2 and (not got or np.mean([w[5] for w in got2]) > np.mean([w[5] for w in got])):
                got = got2
        txt = "".join(w[4] for w in sorted(got, key=lambda w: w[0])).strip()
        if twice and (wb_ - wa) > 120:
            # THE SECOND ENGINE ON A FILE NAME: the first drops underscores
            # and reads a stroke as a dot; tesseract keeps them. Where the
            # two agree once folded and only the second has the underscores,
            # the second stands.
            alt = tess_word(crop)
            fa, fb = re.sub(r"[^a-z0-9]", "", alt.lower()), re.sub(r"[^a-z0-9]", "", txt.lower())
            if alt and (not txt or ("_" in alt and "_" not in txt and _close(fa, fb))):
                txt = alt
        if txt:
            words.append(txt); scores.extend(w[5] for w in got)
        else:
            blank += 1
    return " ".join(words), (float(np.mean(scores)) if scores else 0.0), blank

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
    im = Image.fromarray(rgb_crop).convert("L")
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

def read_frame(path, out_dir, title_hint="memory"):
    rgb, g = load(path)
    H, W = g.shape
    wb = window_box(path, g, title_hint) or [0, int(0.125 * H), int(0.62 * W), int(0.746 * H)]
    x0, y0, x1, y1 = wb
    xl = divider(g, wb)
    hdr_top, hdr_bot, cols = find_header(rgb, xl, x1, wb)
    if hdr_bot is None:
        hdr_top, hdr_bot = y0 + int(0.1 * (y1 - y0)), y0 + int(0.14 * (y1 - y0))
    border = bottom_border(g, wb, xl)
    list_top = hdr_bot + 4
    bands_ = ink_bands(rgb, xl, x1, list_top, border - 4)
    centers = [(a + b) / 2.0 for a, b in bands_]
    gaps = np.diff(centers)
    pitch = int(np.median(gaps)) if len(gaps) else int(1.8 * np.median([b - a for a, b in bands_])) if bands_ else 40
    # the pathbar is one row's height above the bottom border; the list ends above it
    path_top = border - int(1.1 * pitch) if border < y1 + 2 else y1
    list_bot = path_top - 2
    bands_ = [(a, b) for a, b in bands_ if a < list_bot - 4]
    band_h = int(np.median([b - a for a, b in bands_])) if bands_ else pitch // 2
    name_left = cols[0][0] if cols else xl + 60
    ic0, ic1 = max(xl, name_left - int(0.9 * pitch)), name_left - 4
    col_lefts = [c[0] for c in cols] + [x1]
    out_rows = []
    for (a, b) in bands_:
        cy = (a + b) / 2.0
        ry0, ry1 = int(cy - pitch / 2.0), int(cy + pitch / 2.0)
        cut = (a - list_top <= 12) or (list_bot - b <= 12) or ((b - a) < 0.75 * band_h)
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
    thumb = shapes.scroll_thumb(path, [name_left, hdr_bot, x1, path_top])
    side = shapes.scroll_thumb(path, [max(0, xl - 400), y0, xl - 6, y1], reach=min(400, max(40, xl - 6)))
    rec = {"frame": os.path.basename(path), "window": wb, "divider": int(xl), "header": [int(hdr_top), int(hdr_bot)], "path_top": int(path_top),
           "pitch": pitch, "columns": cols, "rows": out_rows, "thumb": thumb, "side_thumb": side}
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    with open(os.path.join(out_dir, stem + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    im = Image.fromarray(rgb).crop((x0, y0, x1, y1)); d = ImageDraw.Draw(im)
    d.rectangle((xl - x0, 0, xl - x0 + 2, y1 - y0), fill=(255, 0, 255))
    d.line((0, hdr_bot - y0, x1 - x0, hdr_bot - y0), fill=(0, 200, 255), width=2)
    d.line((0, hdr_top - y0, x1 - x0, hdr_top - y0), fill=(0, 120, 255), width=1)
    d.line((0, path_top - y0, x1 - x0, path_top - y0), fill=(0, 200, 255), width=2)
    for cl, t_ in cols:
        d.line((cl - x0, hdr_top - y0, cl - x0, path_top - y0), fill=(255, 200, 0), width=1)
    for r in out_rows:
        col = (255, 80, 80) if r["cut"] else ((80, 255, 80) if r["selected"] else (80, 160, 255))
        d.rectangle((name_left - 6 - x0, r["y"][0] - y0, x1 - 8 - x0, r["y"][1] - y0), outline=col, width=2)
        d.text((name_left - x0 + 4, r["y"][0] - y0 + 2), ("%s | " % r["icon"]) + " | ".join(r["cells"])[:110], fill=(255, 255, 0))
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
