#!/usr/bin/env python3
"""Read an Obsidian file-tree pane from a screenshot, deterministically.

The design in one line: the text comes from OCR, the structure comes from
pixels, and nothing comes from a model's judgment.

How the structure is read, and why it needs no hand-tuning:

  Obsidian draws one faint vertical guide line for every ancestor level a row
  has. A depth-3 row therefore shows exactly three guide lines to its left,
  at fixed pixel columns shared by every row at that depth. So:

      depth            = how many guide-line columns this row shows
      collapsed folder = a wide glyph (the chevron) sits between the last
                         guide line and the name, or OCR read the chevron
                         as a leading character
      expanded folder  = the next row is deeper than this one
      file             = neither of the above

  Every one of those is a count or a comparison, so there is no template to
  match. That is what the previous approach got wrong: it tried to learn the
  shape of a triangle from the picture, and a picture containing only open
  folders can never teach it a closed one.

  The one number that could have been a magic constant — how bright a pixel
  must be to count as part of a line — is measured instead. The brightness
  is swept and the value chosen is the one that best satisfies a rule that
  is always true of a tree: a row's guide lines are the FIRST k columns,
  never columns with a gap in them.

Run: python3 tree_reader.py <sidebar.png> [--json out.json]
"""
import json
import statistics
import sys

import cv2
import numpy as np

LINE_COVERAGE = 0.9    # a guide line is lit down (almost) the whole row
BG_KERNEL = 31         # width of the horizontal opening that estimates background
THIN_MAX = 6           # runs this wide or narrower can be guide lines
BLOB_MIN = 7           # runs this wide or wider are glyphs (chevrons, icons)
GLYPH_COVERAGE = 0.25  # a glyph lights part of the row, not all of it
COLUMN_TOL = 10        # px tolerance when clustering guide-line columns
PITCH_TOL = 0.14       # a file tree's rows are evenly pitched, within 14%
MIN_COLUMN_ROWS = 2    # a column drawn on one row only is noise
CHEVRON_CHARS = "><»›˃˅⌄▸▾▶▼"


# ---------------------------------------------------------------- OCR rows

def ocr_rows(png_path):
    """Rows of the pane: text with its pixel box, top to bottom."""
    from rapidocr_onnxruntime import RapidOCR
    res, _ = RapidOCR()(png_path)
    if not res:
        return []
    rows = []
    for box, text, score in res:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        rows.append({
            "text": text.strip(),
            "x0": int(min(xs)), "x1": int(max(xs)),
            "y0": int(min(ys)), "y1": int(max(ys)),
            "score": float(score),
        })
    rows.sort(key=lambda r: r["y0"])
    return rows


def tree_rows(rows):
    """Keep only the file tree: the largest set of evenly pitched rows.

    A file tree draws every row at one fixed height, so its rows sit on a
    single regular vertical pitch. Window chrome — the menu bar, the tab
    strip, the left ribbon icons — does not, so it falls away without any
    hand-placed crop or magic y value.
    """
    if len(rows) < 3:
        return rows
    ys = [r["y0"] for r in rows]
    diffs = sorted(b - a for a, b in zip(ys, ys[1:]) if 8 < b - a < 400)
    if not diffs:
        return rows
    best = []
    for pitch in set(diffs):
        tol = max(4, int(pitch * PITCH_TOL))
        for start in range(len(rows)):
            chain, i = [start], start
            while True:
                # the BEST candidate, not the first: a stray icon sitting a few
                # pixels off the pitch would otherwise steal the link and drop
                # the real row that follows it
                nxt, best_off = None, None
                for j in range(i + 1, len(rows)):
                    gap = ys[j] - ys[i]
                    if gap > pitch + tol:
                        break
                    off = abs(gap - pitch)
                    if off <= tol and (best_off is None or off < best_off):
                        nxt, best_off = j, off
                if nxt is None:
                    break
                chain.append(nxt)
                i = nxt
            if len(chain) > len(best):
                best = chain
    return [rows[i] for i in best] if len(best) >= 3 else rows


# ------------------------------------------------------------ the gutter

def _runs(values, floor):
    """Contiguous runs at or above a floor, as (start, end, width)."""
    out, on, start = [], False, 0
    for i, v in enumerate(values):
        if not on and v >= floor:
            on, start = True, i
        elif on and v < floor:
            on = False
            out.append((start, i - 1, i - start))
    if on:
        out.append((start, len(values) - 1, len(values) - start))
    return out


def gutter_profile(img, row):
    """Column coverage of the strip left of this row's text."""
    y0, y1 = max(0, row["y0"]), min(img.shape[0], row["y1"])
    x1 = max(1, row["x0"])
    band = img[y0:y1, 0:x1]
    if band.size == 0:
        return None
    return band


def is_dark_theme(img):
    """Dark theme when the pane's commonest value is a dark one."""
    return float(np.median(img)) < 128


def local_contrast(band, dark_theme=True):
    """The gutter with its own background removed.

    A horizontal opening wipes out anything narrower than the kernel, leaving
    the background the UI painted — including the selection highlight on
    whichever file is open. What stands out from that is the thin structure:
    guide lines and chevrons.

    Which way it stands out depends on the theme, and the theme is decided
    once for the whole pane rather than guessed per row. In a dark theme the
    guide lines are BRIGHTER than their background; in a light theme they are
    DARKER. Looking only for brighter lines finds one column instead of four
    on a light theme and rebuilds the tree wrongly WITHOUT COMPLAINING, which
    is the worst way for this to fail. Taking both directions at once fixes
    that but blunts the dark case, because the dark fringe around bright text
    then reads as structure too. So: pick the direction, once, from the pane.
    """
    k = np.ones((1, BG_KERNEL), np.uint8)
    if dark_theme:
        return cv2.subtract(band, cv2.morphologyEx(band, cv2.MORPH_OPEN, k))
    return cv2.subtract(cv2.morphologyEx(band, cv2.MORPH_CLOSE, k), band)


def lines_and_glyphs(band, margin, dark_theme=True):
    """Split the gutter into guide lines and glyphs.

    Coverage, not brightness, separates them: a guide line stands above its
    background down the full height of the row, a chevron or icon only part
    of it.
    """
    cov = (local_contrast(band, dark_theme) > margin).mean(axis=0)
    lines = [r for r in _runs(cov, LINE_COVERAGE) if r[2] <= THIN_MAX]
    glyphs = [r for r in _runs(cov, GLYPH_COVERAGE) if r[2] >= BLOB_MIN]
    return lines, glyphs


def _columns_from(all_lines):
    """Cluster per-row line runs into the pane's guide columns.

    A column drawn beside EVERY row is a border, not a guide line — the window
    edge or the ribbon divider. A real guide line marks an ancestor level, so
    the shallowest rows in the pane do not have it. That difference is what
    separates the two, and it works where position cannot: the first guide
    line sits to the LEFT of a root row's name, because a root's own arrow
    occupies that space.
    """
    seen = sorted(a for lines in all_lines for a, b, w in lines)
    if not seen:
        return []
    groups, cur = [], [seen[0]]
    for x in seen[1:]:
        if x - cur[-1] <= COLUMN_TOL:
            cur.append(x)
        else:
            groups.append(cur)
            cur = [x]
    groups.append(cur)
    cols = [int(np.median(g)) for g in groups if len(g) >= MIN_COLUMN_ROWS]

    n = len(all_lines)
    keep = []
    for c in cols:
        drawn = sum(1 for lines in all_lines
                    if any(abs(a - c) <= COLUMN_TOL for a, b, w in lines))
        if drawn < n:
            keep.append(c)
    return evenly_spaced(keep)


def evenly_spaced(cols, tol=0.30):
    """Keep the columns that sit on one regular grid.

    A tree indents every level by the same amount, so its guide lines are
    evenly spaced. Anything at an odd distance from the run — a stray mark in
    the ribbon, a stripe of window chrome — is not part of the grid and is
    dropped. Without this a single outlier makes the whole reading invalid and
    forces the calibration onto a worse setting that sees fewer levels.
    """
    if len(cols) < 3:
        return cols
    gaps = [b - a for a, b in zip(cols, cols[1:])]
    step = statistics.median(gaps)
    if step <= 0:
        return cols
    best = []
    for i in range(len(cols)):
        run = [cols[i]]
        for j in range(i + 1, len(cols)):
            if abs((cols[j] - run[-1]) - step) <= step * tol:
                run.append(cols[j])
        if len(run) > len(best):
            best = run
    return best if len(best) >= 2 else cols


def _present(lines, columns):
    return [c for c in columns
            if any(abs(a - c) <= COLUMN_TOL for a, b, w in lines)]


def calibrate_margin(bands, dark_theme=True, candidates=range(3, 41)):
    """Choose the contrast margin from the image, not from a constant.

    Two rules that always hold in a rendered tree do the filtering: the guide
    lines a row shows are the FIRST k columns with no gaps, and depth can
    only ever step down freely but up by one at a time, since a child cannot
    appear without its parent drawn above it.

    Among the margins that satisfy both, the right one is not the highest
    scoring — it is the most STABLE. A well separated signal produces a wide
    plateau of margins that all give the identical answer, while a fluke
    gives a single isolated value. So the plateaus are found and the widest,
    richest one wins, and its middle is used: the furthest point from either
    edge where the reading changes.
    """
    valid = {}
    for margin in candidates:
        all_lines = [lines_and_glyphs(b, margin, dark_theme)[0] for b in bands]
        cols = _columns_from(all_lines)
        if not cols:
            continue
        depths = []
        ok = True
        for lines in all_lines:
            pres = _present(lines, cols)
            if pres != cols[:len(pres)]:
                ok = False
                break
            depths.append(len(pres))
        if not ok:
            continue
        if any(b > a + 1 for a, b in zip(depths, depths[1:])):
            continue
        valid[margin] = (tuple(depths), cols)

    if not valid:
        return None, []

    # group neighbouring margins that read the tree identically
    plateaus, cur = [], []
    for margin in sorted(valid):
        if cur and margin == cur[-1] + 1 and valid[margin][0] == valid[cur[0]][0]:
            cur.append(margin)
        else:
            if cur:
                plateaus.append(cur)
            cur = [margin]
    if cur:
        plateaus.append(cur)

    def rank(pl):
        """Most levels first, stability second.

        Every candidate here already satisfies both tree invariants, so a
        setting that resolves more guide lines has found real structure the
        others missed rather than invented any — a noise column would have
        broken the prefix rule and been thrown out already. Between two that
        resolve the same structure, the wider plateau is the safer place to
        sit.
        """
        depths, cols = valid[pl[0]]
        return (len(cols), len(pl))

    best = max(plateaus, key=rank)
    pick = best[len(best) // 2]
    return pick, valid[pick][1]


# -------------------------------------------------------------- the read

def left_edge(rows):
    """Where the tree's own text begins, immune to a stray icon.

    Rows at the shallowest level share one left edge, so the tree's edge is
    the smallest x0 that at least two rows agree on. Taking the plain minimum
    instead lets a single ribbon icon that survived the pitch filter drag the
    edge leftward, which turns the pane border into a phantom guide line and
    shifts every depth in the tree by one.
    """
    xs = sorted(r["x0"] for r in rows)
    if not xs:
        return 0
    group = [xs[0]]
    for x in xs[1:]:
        if x - group[-1] <= COLUMN_TOL:
            group.append(x)
        else:
            if len(group) >= 2:
                return int(np.median(group))
            group = [x]
    return int(np.median(group)) if group else xs[0]


def strip_chevron(text):
    """Return (name, ocr_saw_chevron) - OCR sometimes reads the arrow as text."""
    t = text.strip()
    saw = False
    while t and t[0] in CHEVRON_CHARS:
        t = t[1:].strip()
        saw = True
    return t, saw


def read_tree(png_path):
    img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"cannot read {png_path}")
    every = ocr_rows(png_path)
    if not every:
        return {"source": png_path, "rows": []}
    rows = tree_rows(every)
    chrome_dropped = len(every) - len(rows)

    edge = left_edge(rows)
    # a lone icon far left of the tree's own edge is chrome, not a row
    rows = [r for r in rows if r["x0"] >= edge - COLUMN_TOL]
    chrome_dropped = len(every) - len(rows)
    bands = [gutter_profile(img, r) for r in rows]
    keep = [(r, b) for r, b in zip(rows, bands) if b is not None]
    rows = [r for r, _ in keep]
    bands = [b for _, b in keep]

    dark = is_dark_theme(img)
    margin, columns = calibrate_margin(bands, dark)
    if margin is None:
        margin, columns = 8, []

    out = []
    for r, band in zip(rows, bands):
        lines, glyphs = lines_and_glyphs(band, margin, dark)
        present = _present(lines, columns)
        depth = len(present)
        last_guide = max(present) if present else -1
        blob = any(a > last_guide for a, b, w in glyphs)
        name, ocr_chevron = strip_chevron(r["text"])
        out.append({
            "name": name, "raw": r["text"], "depth": depth,
            "collapsed_signal": bool(blob or ocr_chevron),
            "x0": r["x0"], "x1": r["x1"],
            "y0": r["y0"], "y1": r["y1"], "score": r["score"],
            "guides": present,
        })

    # an expanded folder is one whose next row is deeper: pure comparison
    for i, row in enumerate(out):
        deeper_next = (i + 1 < len(out)) and out[i + 1]["depth"] > row["depth"]
        if deeper_next:
            row["kind"], row["chevron"] = "folder", "down"
        elif row["collapsed_signal"]:
            row["kind"], row["chevron"] = "folder", "right"
        else:
            row["kind"], row["chevron"] = "file", None

    ys = [r["y0"] for r in rows]
    pitch = statistics.median([b - a for a, b in zip(ys, ys[1:])]) if len(ys) > 2 else 0
    ok, why = looks_like_a_tree(len(rows), len(every), columns, pitch)
    return {"source": png_path, "guide_columns": columns,
            "theme": "dark" if dark else "light",
            "contrast_margin": margin, "chrome_rows_dropped": chrome_dropped,
            "is_tree": ok, "layout_verdict": why, "row_pitch": pitch,
            "rows": out if ok else []}


def looks_like_a_tree(rows_kept, rows_seen, columns, pitch):
    """Decide whether this pane is a tree at all, and say so when it is not.

    Reading a tree out of something that is not one is the worst outcome
    available: the answer comes back confident and wrong. On a file list with
    columns — a Finder window, a table — the column edges pass for guide lines
    and the result reads like a nesting that was never there.

    Two things separate them. A tree's rows are the bulk of what is in its
    pane, where a column layout leaves most of the text unaccounted for. And a
    tree indents by roughly the height of a row, where column positions are
    spaced by whatever the columns happen to need.
    """
    if rows_seen and rows_kept / rows_seen < 0.5:
        return False, (f"only {rows_kept} of {rows_seen} rows sit on one pitch; "
                       "a tree's rows are the bulk of its pane")
    if len(columns) >= 2 and pitch:
        step = statistics.median([b - a for a, b in zip(columns, columns[1:])])
        if not (0.25 * pitch <= step <= 2.5 * pitch):
            return False, (f"indent step {step:.0f}px against row pitch "
                           f"{pitch:.0f}px; that spacing is columns, not nesting")
    return True, "rows evenly pitched and indented like a tree"


def render(tree):
    """Draw the tree the way Obsidian shows it, for eyeballing against a frame."""
    if not tree.get("is_tree", True):
        return f"NOT A TREE VIEW - {tree.get('layout_verdict')}"
    lines = []
    for r in tree["rows"]:
        mark = {"down": "˅", "right": "˃"}.get(r["chevron"], " ")
        lines.append("│ " * r["depth"] + f"{mark} {r['name']}")
    return "\n".join(lines)


def main():
    png = sys.argv[1]
    tree = read_tree(png)
    print(f"guide columns {tree.get('guide_columns')} at contrast margin "
          f"{tree.get('contrast_margin')}; chrome rows dropped "
          f"{tree.get('chrome_rows_dropped')}; verdict: "
          f"{tree.get('layout_verdict')}")
    print(render(tree))
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        with open(out, "w") as fh:
            json.dump(tree, fh, indent=2)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
