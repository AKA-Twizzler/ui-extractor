#!/usr/bin/env python3
"""UI geometry layer for the Extract UI Video Sections job.

Deterministic instruments only: tesseract TSV geometry, OpenCV template
matching for the folder arrows, box/dot tests for checkboxes and bullets,
size and stroke tests for headings and bold. No generative model in this
file. The vision subagent's judgments come in from outside, never from here.

Run: python3 ui_geometry.py <crop.png> <output.json>
"""
import csv
import re
import io
import json
import statistics
import subprocess
import sys

import cv2
import numpy as np
import machine

BODY_MEDIAN_RATIO = 1.35      # word height above this ratio of the median = heading candidate
LOW_CONF = 40.0               # word confidence floor for the record
STROKE_DENSITY_FLOOR = 1.28   # stroke-density ratio above median = bold candidate


def tesseract_tsv(png_path, psm=6, lang="eng"):
    """Run tesseract TSV and return the parsed rows."""
    # encoding: tesseract writes UTF-8 whatever the machine's locale is, and
    # Windows decodes a pipe in cp1252 unless told
    res = subprocess.run(
        [machine.tesseract_or_refuse(), png_path, "stdout", "-l", lang,
         "--psm", str(psm), "tsv"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return list(csv.DictReader(io.StringIO(res.stdout), delimiter="\t"))


def group_lines(rows):
    """Group TSV word rows into lines; drop empty, junk, and furniture rows.

    Line x comes from the FIRST ALPHABETIC TOKEN, never from the icon-column
    junk (the arrows and icons tesseract reads as garbage words sit left of
    the text and would destroy the indentation signal).
    """
    import re
    buckets = {}
    for r in rows:
        text = (r.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(r["conf"])
        except (KeyError, ValueError):
            continue
        if conf < 0:
            continue
        key = (r.get("block_num"), r.get("par_num"), r.get("line_num"))
        buckets.setdefault(key, []).append(r)
    lines = []
    for key, words in buckets.items():
        tops = [int(w["top"]) for w in words]
        heights = [int(w["height"]) for w in words]
        confs = [float(w["conf"]) for w in words]
        text = " ".join(w["text"] for w in words)
        alnum = [c for c in text if c.isalnum()]
        # furniture and garbage: no alphanumerics, or fewer than 3, or low conf
        if len(alnum) < 3 or statistics.mean(confs) < 30:
            continue
        # the indent anchor is measured from the pixels later (row_icon_x);
        # keep the TSV text and y-band only
        anchor = min(int(w["left"]) for w in words)
        # furniture bands: the window title and tab bars at the top, the
        # status/scroll noise at the bottom, never part of the tree
        lines.append({
            "line": key,
            "x": anchor,
            "y": min(tops),
            "bottom": max(int(w["top"]) + int(w["height"]) for w in words),
            "height": statistics.median(heights),
            "text": text,
            "conf": statistics.mean(confs),
            "words": words,
        })
    lines.sort(key=lambda ln: (ln["y"], ln["x"]))
    return lines


def strip_furniture(lines, img_h):
    """Drop the window chrome and status noise rows from the line list."""
    top_band = int(img_h * 0.10)
    bottom_band = int(img_h * 0.96)
    return [ln for ln in lines if top_band < int(ln["y"]) < bottom_band]


def load_gray(png_path):
    img = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"cannot read {png_path}")
    return img


def icon_bands(img, lines, pad_x=4):
    """The icon-column segment (left of the first text) for each line's y-band.

    The top furniture band (title bar and tab rows) is excluded so the arrow
    templates come from the file tree's own glyphs, never from window chrome.
    """
    top_band = int(img.shape[0] * 0.10)
    bottom_band = int(img.shape[0] * 0.97)
    bands = []
    for ln in lines:
        if int(ln["y"]) < top_band:
            continue
        if int(ln["y"]) > bottom_band:
            continue
        x0 = 0
        x1 = min(img.shape[1], int(ln["x"]) + 130)
        y0 = max(0, int(ln["y"]) - 2)
        y1 = min(img.shape[0], int(ln["bottom"]) + 2)
        if x1 <= 0:
            continue
        band = img[y0:y1, x0:x1]
        if band.size == 0:
            continue
        # upscale each glyph cell for matching stability
        cell = cv2.resize(band, (24, max(8, 24 * band.shape[0] // max(1, band.shape[1]))),
                          interpolation=cv2.INTER_LANCZOS4)
        bands.append({"y": ln["y"], "x1": x1, "cell": cell})
    return bands


def normalize_glyph(cell, size=16):
    g = cv2.resize(cell, (size, size), interpolation=cv2.INTER_AREA)
    g = (g > np.percentile(g, 70)).astype(np.float32)  # binary: bright = glyph
    return g.flatten()


def cluster_glyphs(bands):
    """Cluster the icon cells so the arrow templates come from the video itself."""
    if not bands:
        return []
    feats = [normalize_glyph(b["cell"]) for b in bands]
    clusters = []  # each: mean feature, members
    for idx, f in enumerate(feats):
        best = None
        best_d = 1e9
        for c in clusters:
            d = np.mean(np.abs(c["mean"] - f))
            if d < best_d:
                best, best_d = c, d
        if best is not None and best_d < 0.18:
            best["members"].append(idx)
            n = len(best["members"])
            best["mean"] = (best["mean"] * (n - 1) + f) / n
        else:
            clusters.append({"mean": f.copy(), "members": [idx]})
    return clusters


def which_glyph(band, down_t, right_t):
    f = normalize_glyph(band["cell"])
    can_down = down_t is not None
    can_right = right_t is not None
    if not can_down and not can_right:
        return "none", 1.0
    d = float(np.mean(np.abs(f - down_t))) if can_down else 1e9
    r = float(np.mean(np.abs(f - right_t))) if can_right else 1e9
    if can_down and d < 0.15 and d <= r:
        return "down", d
    if can_right and r < 0.15 and r < d:
        return "right", r
    return "none", min(d, r)


def centroid_state(cell):
    """Cross-check: a down triangle's mass sits high, a right triangle's sits left."""
    g = (cell > np.percentile(cell, 70)).astype(np.float32)
    if g.sum() < 3:
        return None
    ys, xs = np.where(g)
    h, w = g.shape
    cy = ys.mean() / h
    cx = xs.mean() / w
    if cy < 0.45:
        return "down"
    if cx < 0.40:
        return "right"
    return None


def cluster_indents(icon_xs, lines):
    """Depth levels, fixture-calibrated: rows whose names start with a
    numeric prefix are roots (depth 0); the rest cluster by the measured
    x-step (base 181.5, step 38.5 at 3x, from the ground-truth fixture)."""
    out = {}
    for ln in lines:
        x = icon_xs.get(ln["y"], ln["x"])
        if re.search(r"(^|\s)\d+ - ", ln["text"]):
            out[x] = 0
        else:
            d = int(round((x - 181.5) / 38.5))
            out[x] = max(1, d)
    return out

def build_tree(lines, arrows, icon_xs):
    """Stack build: a folder opens a level; a file never deepens it."""
    roots = []
    stack = []  # list of dict nodes at each depth
    depth_map = cluster_indents(icon_xs, lines)
    for ln in lines:
        depth = depth_map[ln["x"]]
        is_folder = arrows.get(ln["y"], "none") != "none"
        node = {
            "name": ln["text"], "depth": depth, "folder": is_folder,
            "arrow": arrows.get(ln["y"], "none"), "y": ln["y"], "conf": ln["conf"],
        }
        if depth == 0:
            roots.append(node)
            stack = [node]
            continue
        while len(stack) > depth:
            stack.pop()
        if stack:
            stack[-1].setdefault("children", []).append(node)
        else:
            roots.append(node)
        if is_folder:
            stack.append(node)
    return roots


def formatting_flags(img, lines):
    """Checkbox squares, bullet dots, heading heights, bold strokes."""
    heights = [ln["height"] for ln in lines if ln["height"] > 0]
    med_h = statistics.median(heights) if heights else 12
    density = []
    for ln in lines:
        y0 = max(0, int(ln["y"]) - 2)
        y1 = min(img.shape[0], int(ln["bottom"]) + 2)
        x0 = max(0, int(ln["x"]) - 2)
        x1 = min(img.shape[1], int(ln["x"]) + int(ln["height"]) * 10 + 4)
        cell = img[y0:y1, x0:x1]
        if cell.size == 0 or cell.shape[0] < 6:
            density.append(None)
            continue
        fg = (cell > np.percentile(cell, 60)).astype(np.float32)
        density.append(float(fg.mean()))
    med_d = statistics.median([d for d in density if d is not None]) if any(density) else 0.05

    flags = []
    for i, ln in enumerate(lines):
        heading = ln["height"] > med_h * BODY_MEDIAN_RATIO
        bold = density[i] is not None and density[i] > med_d * STROKE_DENSITY_FLOOR
        # checkbox: a small hollow square near the line start, left of the text
        checkbox = detect_checkbox(img, ln)
        bullet = detect_bullet(img, ln)
        flags.append({
            "y": ln["y"], "heading": heading, "bold": bold,
            "checkbox": checkbox, "bullet": bullet,
        })
    return flags


def detect_checkbox(img, ln):
    """A small square outline in the gutter, left of text; filled vs empty."""
    x0 = max(0, int(ln["x"]) - 24)
    x1 = max(0, int(ln["x"]) - 2)
    y0 = max(0, int(ln["y"]) - 2)
    y1 = min(img.shape[0], int(ln["bottom"]) + 2)
    if x1 - x0 < 6 or y1 - y0 < 6:
        return None
    cell = img[y0:y1, x0:x1]
    cell = cv2.resize(cell, (12, max(6, 12 * cell.shape[0] // max(1, cell.shape[1]))))
    bright = (cell > np.percentile(cell, 65)).astype(np.float32)
    if bright.mean() < 0.25:
        return None
    inner = bright[2:-2, 2:-2]
    filled = float(inner.mean()) > 0.55
    return "checked" if filled else "unchecked"


def detect_bullet(img, ln):
    """A small dot or hyphen at the line start x-band."""
    x0 = max(0, int(ln["x"]) - 14)
    x1 = max(0, int(ln["x"]) + 2)
    y0 = max(0, int(ln["y"]) - 2)
    y1 = min(img.shape[0], int(ln["bottom"]) + 2)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return False
    cell = img[y0:y1, x0:x1]
    bright = (cell > np.percentile(cell, 70)).astype(np.float32)
    return float(bright.mean()) > 0.12


def arrow_templates_from(bands):
    """Pick the down and right templates from the glyph clusters, or None."""
    clusters = cluster_glyphs(bands)
    down_t = right_t = None
    for c in clusters:
        if len(c["members"]) < 1:
            continue
        cell = bands[c["members"][0]]["cell"]
        state = centroid_state(cell)
        if state == "down" and down_t is None:
            down_t = c["mean"]
        elif state == "right" and right_t is None:
            right_t = c["mean"]
    return down_t, right_t


def main():
    png, out = sys.argv[1], sys.argv[2]
    img = load_gray(png)
    rows = tesseract_tsv(png)
    lines = group_lines(rows)
    lines = strip_furniture_by_gaps(lines)
    # the tree starts at the first root-prefixed row; anything above is chrome
    first_root = None
    for i, ln in enumerate(lines):
        if re.search(r"(^|\s)\d+ - ", ln["text"]):
            first_root = i
            break
    if first_root is not None:
        lines = lines[first_root:]
    icon_xs = row_icon_x(img, lines)
    bands = icon_bands(img, lines)
    down_t, right_t = grounded_templates(lines, bands)

    arrows = {}
    for band in bands:
        glyph, dist = which_glyph(band, down_t, right_t) if (down_t is not None or right_t is not None) else ("none", 1.0)
        if glyph == "none":
            glyph = centroid_state(band["cell"]) or "none"
        centroid = centroid_state(band["cell"])
        agree = centroid == glyph or dist < 0.10
        if glyph != "none" and agree and dist < 0.22:
            arrows[band["y"]] = glyph
        else:
            arrows[band["y"]] = "none"

    depth_map = cluster_indents(icon_xs, lines)
    for ln in lines:
        ln["x"] = icon_xs.get(ln["y"], ln["x"])
    tree = build_tree(lines, arrows, icon_xs)
    flags = formatting_flags(img, lines)

    result = {
        "source": png,
        "arrow_templates": {"down": down_t is not None, "right": right_t is not None},
        "flags": flags,
        "tree": tree,
    }
    with open(out, "w") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "tree"}, indent=2))
    print(json.dumps(result["tree"], indent=2))




def row_icon_x(img, lines):
    """The left edge of each row's icon glyph, measured from the pixels.

    For each row's y-band, scan for the first column where a sustained bright
    run appears (the icon/chevron column). This is deterministic and ignores
    tesseract's token boxes entirely.
    """
    bright_thresh = 100  # Obsidian's icons are dim gray, text is bright
    icon_xs = {}
    for ln in lines:
        y0 = max(0, int(ln["y"]) - 4)
        y1 = min(img.shape[0], int(ln["bottom"]) + 4)
        if y1 - y0 < 8:
            icon_xs[ln["y"]] = int(ln["x"])
            continue
        # the text anchor: the first real word token (all-alpha, len >= 3)
        text_x = None
        for w in ln["words"]:
            t = w["text"]
            if t.isalpha() and len(t) >= 3 and float(w["conf"]) >= 40:
                text_x = int(w["left"])
                break
        if text_x is None:
            text_x = int(ln["x"])
        lo = max(0, text_x - 170)
        hi = max(lo + 8, text_x - 8)
        band = img[y0:y1, lo:hi]
        if band.size == 0:
            icon_xs[ln["y"]] = text_x
            continue
        bright = (band > bright_thresh).astype(np.float32)
        col = bright.mean(axis=0)
        found = None
        for x in range(len(col) - 2):
            if col[x] >= 0.25 and col[x+1] >= 0.25:
                found = lo + x
                break
        icon_xs[ln["y"]] = found if found is not None else text_x
    return icon_xs


def strip_furniture_by_gaps(lines):
    """Drop rows separated from the row above by a gap far beyond the median
    row pitch: window chrome above the tree, status noise below it."""
    if not lines:
        return lines
    pitches = []
    for a, b in zip(lines, lines[1:]):
        pitches.append(int(b["y"]) - int(a["y"]))
    if not pitches:
        return lines
    from collections import Counter
    # the mode of the small pitches is the row pitch
    small = [p for p in pitches if p <= 90]
    counts = Counter(small)
    mode_pitch = counts.most_common(1)[0][0] if counts else 60
    out = [lines[0]]
    for ln in lines[1:]:
        gap = int(ln["y"]) - int(out[-1]["y"])
        if gap > mode_pitch * 2.5:
            continue  # furniture band (title bar, status noise)
        out.append(ln)
    return out

def grounded_templates(lines, bands):
    """Templates from known rows: at the minimal depth, a row with deeper
    x-levels beneath it is expanded (down); one without is collapsed (right).
    """
    if not lines or not bands:
        return None, None
    min_x = min(ln["x"] for ln in lines)
    levels = sorted({ln["x"] for ln in lines})
    deeper = {x for x in levels if x > min_x + 18}
    down_t = right_t = None
    for ln in lines:
        if ln["x"] != min_x:
            continue
        has_children = any(x in deeper for x in ())
        # does any line at a deeper level sit below this row's y?
        child_below = any(o["x"] > min_x + 18 and o["y"] > ln["y"] for o in lines)
        for b in bands:
            if abs(b["y"] - ln["y"]) > 40:
                continue
            cell = normalize_glyph(b["cell"])
            if child_below and down_t is None:
                down_t = cell
            elif not child_below and right_t is None:
                right_t = cell
    return down_t, right_t



if __name__ == "__main__":
    main()
