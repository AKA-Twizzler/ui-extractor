"""Pixels first, words second: one Finder list window read from its picture.

The structure comes from the pixels alone -- the window's rectangle, the
sidebar's dividing line, the toolbar and header bands, the rows from the
list's own stripes, the selected band from its colour, the icons from
their colour, the columns from the header's words, the thumb from its
bar -- and only then are the words read, row by row, into that structure.
Run under the Windows venv (cv2, rapidocr):
    python _probe/pixfirst.py <frame.png> <out_dir> [<title>]
"""
import json, os, sys
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
    col = np.median(band, axis=0)          # the median: icons and words are sparse, the background is not
    sm = np.convolve(col, np.ones(9) / 9, mode="same")
    st = [(i, d) for i, d in steps(sm, 2.5) if d < 0 and i > 8]
    if not st:
        return x0
    i, d = min(st, key=lambda s: s[1])
    return x0 + i

def ink_bands(rgb, xl, x1, y0, y1, least=2):
    """The rows of writing on the list side, from the ink itself: runs of
    rows holding light pixels (text and white icons; a green band's own
    colour is not ink). [(top, bottom)] in frame pixels."""
    c = rgb[y0:y1, xl + 20:x1 - 20]
    ink = c.min(axis=2) > 100
    cnt = ink.sum(axis=1)
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
            merged = [(s_, e_) for s_, e_ in merged if e_ - s_ >= 20]
            names = [w[4].strip() for w in sorted(words, key=lambda w: w[0])]
            cols = [(xl + s_, names[k] if k < len(names) else "") for k, (s_, e_) in enumerate(merged)]
            return a, b, cols
    return None, None, []

def pathbar_top(g, wb, xl):
    """The pathbar's top line: the strongest step in the bottom tenth of the list side."""
    x0, y0, x1, y1 = wb
    h = y1 - y0
    strip = g[y1 - h // 10:y1, xl + 40:x1 - 40].mean(axis=1)
    sm = np.convolve(strip, np.ones(3) / 3, mode="same")
    st = steps(sm, 3.0)
    return y1 - h // 10 + (min(st, key=lambda s: s[0])[0] if st else h // 10 - 60)

def header_columns(rgb, xl, x1, hdr_top, hdr_bot):
    """The column lefts from the header's words."""
    crop = rgb[hdr_top:hdr_bot, xl:x1]
    words = ocr(crop, 2.0)
    cols = []
    for w in sorted(words, key=lambda w: w[0]):
        t = w[4].strip()
        if t and t.lower() != "v" and len(t) > 1:
            cols.append((xl + int(w[0]), t))
    return cols

def icon_of(rgb, y0, y1, x0, x1):
    """What colour the icon at a row's head is: folder (green), md (orange), file (white), or none."""
    c = rgb[y0 + 4:y1 - 4, x0:x1].astype(np.float32)
    if c.size == 0:
        return "none", 0
    r, gg, b = c[:, :, 0], c[:, :, 1], c[:, :, 2]
    lit = (c.max(axis=2) > 90)
    if lit.mean() < 0.02:
        return "none", 0
    rr, gm, bm = r[lit].mean(), gg[lit].mean(), b[lit].mean()
    if gm > rr + 30 and gm > bm + 30:
        return "folder", int(lit.sum())
    if rr > gm + 30 and rr > bm + 40:
        return "md", int(lit.sum())
    return "file", int(lit.sum())

def read_frame(path, out_dir, title_hint="memory"):
    rgb, g = load(path)
    H, W = g.shape
    wb = window_box(path, g, title_hint) or [0, int(0.125 * H), int(0.62 * W), int(0.746 * H)]
    x0, y0, x1, y1 = wb
    xl = divider(g, wb)
    hdr_top, hdr_bot, cols = find_header(rgb, xl, x1, wb)
    if hdr_bot is None:
        hdr_top, hdr_bot = y0 + int(0.1 * (y1 - y0)), y0 + int(0.14 * (y1 - y0))
    path_top = pathbar_top(g, wb, xl)
    list_top, list_bot = hdr_bot + 4, path_top - 2
    bands_ = ink_bands(rgb, xl, x1, list_top, list_bot)
    centers = [(a + b) / 2.0 for a, b in bands_]
    gaps = np.diff(centers)
    pitch = int(np.median(gaps)) if len(gaps) else int(1.8 * np.median([b - a for a, b in bands_])) if bands_ else 40
    band_h = int(np.median([b - a for a, b in bands_])) if bands_ else pitch // 2
    name_left = cols[0][0] if cols else xl + 60
    ic0, ic1 = max(xl, name_left - int(0.9 * pitch)), name_left - 4
    col_lefts = [c[0] for c in cols] + [x1]
    out_rows = []
    for (a, b) in bands_:
        cy = (a + b) / 2.0
        ry0, ry1 = int(cy - pitch / 2.0), int(cy + pitch / 2.0)
        cut = (a - list_top < 3) or (list_bot - b < 3) or ((b - a) < 0.6 * band_h)
        sel_c = rgb[max(a, ry0):min(b, ry1), xl + 200:x1 - 80].astype(np.float32)
        sel = bool(((sel_c[:, :, 1] - np.maximum(sel_c[:, :, 0], sel_c[:, :, 2])) > 25).mean() > 0.4) if sel_c.size else False
        icon, n = icon_of(rgb, max(list_top, ry0), min(list_bot, ry1), ic0, ic1)
        words = ocr(rgb[max(list_top, ry0):min(list_bot, ry1), name_left - 6:x1 - 8], 2.0)
        cells = [""] * max(1, len(col_lefts) - 1)
        for w in sorted(words, key=lambda w: w[0]):
            wx = name_left - 6 + w[0]
            k = max(0, min(len(cells) - 1, sum(1 for cl in col_lefts[1:-1] if wx >= cl - 8)))
            cells[k] = (cells[k] + " " + w[4]).strip()
        out_rows.append({"y": [int(ry0), int(ry1)], "ink": [int(a), int(b)], "selected": sel, "cut": bool(cut), "icon": icon, "cells": cells})
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
        print(("CUT " if r["cut"] else "    ") + ("SEL " if r["selected"] else "    ") + r["icon"].ljust(6), r["y"], " | ".join(r["cells"]))
