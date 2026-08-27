"""The note, drawn as the windows the screen showed, with their content inside.

    python draw2.py <records.jsonl> [<note.md>]

One section per moment; inside it one callout per window, holding what
the window held: the sidebar as a line, the table rebuilt from where the
words sat (rows by height, columns by the header's positions, the
reader's leftovers put back in their cells), a tree as a code block, a
note as its own markdown, the path bar as a line. Markdown wherever
markdown can show it; HTML only for what markdown cannot draw (a colour,
an icon). A moment whose panes all read the same as an earlier one is
one line pointing back. No map, no dump of words under the window; the
doubt is one small line. The moment-by-moment record rides folded at
the end, so nothing the reader said is lost.
"""
import html
import json
import os
import re
import sys

import difflib

import draw as old   # the helpers that do not change: app names, clocks, the loose split
import shapes        # the windows the screen itself drew, to keep panes of different windows apart

SCALE = 3                # the enlargement the structural readers measured in
LONG_SAID = 700          # Jared's words fold past this many characters
MAX_DOUBT = 14           # doubts named in the small line before "and N more"


# ------------------------------------------------------------- small helpers

def cell(s):
    """Text fit for a markdown table cell."""
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s.replace("|", "\\|")


def crumb_like(c):
    """A path crumb is a name: no space (up to 48 letters, a project folder
    can be long), or a Title Case run ("02 Company A (Info Product)");
    never an apostrophe, never a sentence's small words."""
    c = c.rstrip(">").strip()
    if "'" in c or not c:
        return False
    if " " not in c:
        return len(c) <= 48
    return (len(c) <= 40 and c.count(" ") <= 4 and (c[:1].isupper() or c[:1].isdigit())
            and all(w[:1].isupper() or w[:1].isdigit() or w[:1] in "(" for w in c.split()))


def reading_order(items, box_of):
    """Rows top to bottom, left to right within a row; two boxes share a
    row when their centres sit within half a box height of each other."""
    items = sorted(items, key=lambda it: ((box_of(it)[1] + box_of(it)[3]) / 2, box_of(it)[0]))
    rows, cur, cy = [], [], None
    for it in items:
        b = box_of(it)
        c = (b[1] + b[3]) / 2
        h = max(1, b[3] - b[1])
        if cy is not None and c - cy > 0.5 * h:
            rows.append(cur)
            cur, cy = [], None
        cur.append(it)
        if cy is None:
            cy = c
    if cur:
        rows.append(cur)
    return [sorted(r, key=lambda it: box_of(it)[0]) for r in rows]


def strip_note(line):
    """A document line without the reader's doubt suffix; the suffix is
    returned separately for the small line."""
    parts = re.split(r"\s+<- ", line.rstrip())
    return parts[0], [p.strip() for p in parts[1:]]


# ------------------------------------------------------------- what a pane holds

def items_of(pane):
    """Every reading on a pane as a dict: text, box in frame pixels, ok,
    role (head / cell / left / loose) and what the reader knew about it."""
    ox, oy = pane["box"][0], pane["box"][1]
    d = pane.get("data") or {}
    kind = pane["kind"]
    out = []

    def put(text, box, ok=True, role="loose", **extra):
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            return
        it = {"text": text, "box": [float(v) for v in box], "ok": bool(ok), "role": role}
        it.update(extra)
        out.append(it)

    if kind == "text, not a tree":
        # a narrow pane was read enlarged and its boxes came back enlarged;
        # a wide one was read as it stood. A box reaching past the pane's
        # own width or height says which, so the boxes land in frame pixels
        # either way
        reads = [r for r in (d.get("readings") or []) if r.get("box")]
        pw, ph = pane["box"][2] - ox, pane["box"][3] - oy
        big = any(r["box"][2] > 1.2 * pw or r["box"][3] > 1.2 * ph for r in reads)
        s = SCALE if big else 1
        for r in reads:
            b = r["box"]
            put(r["text"], [b[0] / s + ox, b[1] / s + oy, b[2] / s + ox, b[3] / s + oy],
                ok=r.get("confirmed", True), role="loose", hue=r.get("hue"), icon=r.get("icon"),
                large=r.get("large"))
    elif kind == "a list of columns":
        for bi, blk in enumerate(d.get("blocks") or []):
            bands = [[v / SCALE + ox for v in band] for band in (blk.get("bands") or [])]
            hb = blk.get("head_box")
            header = blk.get("header") or []
            headflags = blk.get("headflags") or [None] * len(header)
            if hb:
                hy0, hy1 = hb[1] / SCALE + oy, hb[3] / SCALE + oy
                for i, h in enumerate(header):
                    if i < len(bands) and h:
                        put(h, [bands[i][0], hy0, bands[i][1], hy1], ok=not headflags[i], role="head", col=bands[i])
            flags = blk.get("flags") or []
            styles = blk.get("row_style") or []
            for ri, row in enumerate(blk.get("rows") or []):
                rb = (blk.get("row_boxes") or [None] * len(blk["rows"]))[ri]
                if not rb:
                    continue
                y0, y1 = rb[1] / SCALE + oy, rb[3] / SCALE + oy
                st = styles[ri] if ri < len(styles) and isinstance(styles[ri], dict) else {}
                fl = flags[ri] if ri < len(flags) else [None] * len(row)
                for i, c in enumerate(row):
                    if i < len(bands) and c:
                        put(c, [bands[i][0], y0, bands[i][1], y1], ok=not (fl[i] if i < len(fl) else None),
                            role="cell", col=bands[i], icon=st.get("icon") if i == 0 else None,
                            band=st.get("band"))
        for r in d.get("remainder") or []:
            b = r.get("box")
            if b:
                put(r["text"], [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], ok=r.get("confirmed", False), role="left")
    elif kind == "a file tree":
        for r in d.get("rows") or []:
            put(r.get("name") or r.get("raw") or "", [r["x0"] + ox, r["y0"] + oy, r["x1"] + ox, r["y1"] + oy],
                ok=r.get("name_status") != "uncertain", role="tree", depth=r.get("depth", 0),
                chevron=r.get("chevron"), kind=r.get("kind"))
        for r in d.get("remainder") or []:
            b = r.get("box")
            if b:
                put(r["text"], [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], ok=r.get("confirmed", False), role="left")
    elif kind == "an open document":
        for r in d.get("remainder") or []:
            b = r.get("box")
            if b:
                put(r["text"], [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], ok=r.get("confirmed", False), role="left")
    # A pane is a piece of the frame, so nothing read inside it can reach
    # past its own edges. When the readings do, the pane was read enlarged
    # and came back in the enlarged picture's pixels: how far they overrun
    # is the enlargement, so they are put back at the size they really were.
    # Left alone, a file tree read at twice size drags every window edge
    # measured from it out to twice its true place.
    pw = pane["box"][2] - ox
    ph = pane["box"][3] - oy
    if out and pw > 0 and ph > 0:
        over = max(max((it["box"][2] - ox) / pw for it in out),
                   max((it["box"][3] - oy) / ph for it in out))
        if over > 1.2:
            for it in out:
                b = it["box"]
                it["box"] = [ox + (b[0] - ox) / over, oy + (b[1] - oy) / over,
                             ox + (b[2] - ox) / over, oy + (b[3] - oy) / over]

    # a selection band the reader measured but no row carried: an item whose
    # middle sits inside a row-height band on this pane is on that band
    look_bg = ((d.get("style") or {}).get("look") or {}).get("background") or [0, 0, 0]
    bg_lum = sum(look_bg) / max(1, len(look_bg))
    bands = [b for b in ((d.get("style") or {}).get("bands") or [])
             if b.get("hue") and b["hue"] not in ("black", "white")
             and abs(sum(b.get("colour") or [0]) / max(1, len(b.get("colour") or [0])) - bg_lum) >= 20]
    # a narrow pane was read enlarged, so its bands were measured enlarged
    # too; a band reaching past the pane's own height tells which it is
    tall = max((b.get("y1", 0) for b in bands), default=0)
    band_scale = SCALE if tall > 1.2 * (pane["box"][3] - pane["box"][1]) else 1
    for it in out:
        if it.get("band") or it["role"] == "head":
            continue
        h = it["box"][3] - it["box"][1]
        cy = (it["box"][1] + it["box"][3]) / 2
        hit = next((b for b in bands if b["y0"] / band_scale + oy <= cy <= b["y1"] / band_scale + oy
                    and 0.8 * h <= b["height"] / band_scale <= 3.2 * h), None)
        if hit:
            it["band"] = hit["hue"]
    return out


def tree_band(pane):
    d = pane.get("data") or {}
    rows = d.get("rows") or []
    if not rows:
        return None
    oy = pane["box"][1]
    return (min(r["y0"] for r in rows) + oy, max(r["y1"] for r in rows) + oy)


# ------------------------------------------------------------- the table, rebuilt

def merge_columns(ranges, tol):
    """Column x-ranges clustered by where they start: two bands are one
    column when their left edges sit within `tol` of each other. Touching
    bands are neighbours, never one column."""
    cols = []
    for r in sorted(ranges, key=lambda r: r[0]):
        if cols and abs(r[0] - cols[-1][0]) <= tol:
            cols[-1] = [min(cols[-1][0], r[0]), max(cols[-1][1], r[1])]
        else:
            cols.append([r[0], r[1]])
    return cols


def alike_readings(a, b):
    """Two readings of the same cell: alike once spaces and marks are gone."""
    x = re.sub(r"[^a-z0-9]", "", a.lower())
    y = re.sub(r"[^a-z0-9]", "", b.lower())
    if not x or not y:
        return False
    return x == y or difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.7


def table_rows(cells, rh):
    """Cells grouped into rows by the table's own row height: a cell joins
    the row whose centre sits within half a row of its own."""
    cells = sorted(cells, key=lambda it: ((it["box"][1] + it["box"][3]) / 2, it["box"][0]))
    rows, cur, cy = [], [], None
    for it in cells:
        c = (it["box"][1] + it["box"][3]) / 2
        if cy is not None and c - cy > 0.55 * rh:
            rows.append(cur)
            cur, cy = [], None
        cur.append(it)
        cy = c if cy is None else (cy * (len(cur) - 1) + c) / len(cur)
    if cur:
        rows.append(cur)
    return rows


def build_tables(pane):
    """Every list on the pane, each built by build_table's rules. Two
    Finder windows side by side read as one wide list; a second "Name"
    heading far to the right of the first is the second window's, and the
    items from there on are its own list."""
    items = items_of(pane)
    names = sorted((it for it in items if it["text"] == "Name" and it["role"] in ("head", "left")), key=lambda it: it["box"][0])
    width = pane["box"][2] - pane["box"][0]
    cuts = []
    for a, b in zip(names, names[1:]):
        if b["box"][0] - a["box"][0] > 0.3 * width:
            cuts.append(b["box"][0] - (b["box"][3] - b["box"][1]))
    groups = []
    lo = float("-inf")
    for cut in cuts + [float("inf")]:
        groups.append([it for it in items if lo <= (it["box"][0] + it["box"][2]) / 2 < cut])
        lo = cut
    out = []
    spill = []
    for g in groups:
        g = spill + g
        spill = []
        built = _build_table(g, spill)
        if not built and any(it["role"] == "left" for it in g):
            built = table_from_items(g)       # the second window: words only
        if built:
            out.append(built)
    return out


def build_table(pane):
    """The pane's list, as the screen showed it (the biggest when the pane
    held two windows' lists)."""
    tables = build_tables(pane)
    return max(tables, key=lambda t: len(t[3])) if tables else None


def _build_table(items, spill=None):
    """The table as the screen showed it: rows by height, columns by the
    header's positions, and the reader's leftovers put back where they sat.
    Words beyond the last column's reach are another window's; they go to
    `spill` when given.

    Returns (top_items, side_items, header, rows, bottom_items, doubts);
    rows are lists of (cells, icon, band)."""
    cells = [it for it in items if it["role"] in ("head", "cell")]
    left = [it for it in items if it["role"] == "left"]
    doubts = []
    if not cells:
        return None
    heights = sorted(it["box"][3] - it["box"][1] for it in cells)
    rh = heights[len(heights) // 2] or 20
    cols = merge_columns([it["col"] for it in cells], tol=1.5 * rh)
    x_lo, x_hi = cols[0][0], cols[-1][1]
    bound = min(x_hi + rh, x_lo + 12 * rh if len(cols) == 1 else cols[-1][0] + 12 * rh)
    beyond = [it for it in left if it["box"][0] > bound]
    left = [it for it in left if it["box"][0] <= bound]
    if spill is not None:
        spill.extend(beyond)
    y_lo = min(it["box"][1] for it in cells)
    y_hi = max(it["box"][3] for it in cells)
    top, side, bottom, inside = [], [], [], []
    for it in left:
        cx = (it["box"][0] + it["box"][2]) / 2
        cy = (it["box"][1] + it["box"][3]) / 2
        if it["box"][2] <= x_lo - rh and cy >= y_lo - rh:
            side.append(it)
        elif it["box"][3] <= y_lo - 0.3 * rh:
            it["above"] = (y_lo - it["box"][3]) / rh     # rows above the list's top
            top.append(it)
        elif it["box"][1] >= y_hi + 0.3 * rh:
            bottom.append(it)
        else:
            inside.append(it)
    # a leftover inside the table's band joins a column by its x, or opens one
    for it in inside:
        cx = (it["box"][0] + it["box"][2]) / 2
        hit = next((c for c in cols if c[0] - rh <= cx <= c[1] + rh), None)
        if hit is None:
            hit = [it["box"][0], it["box"][2]]
            cols.append(hit)
            cols.sort(key=lambda c: c[0])
        it["col"] = hit
        it["role"] = "cell"
    cells = cells + inside
    rows = table_rows(cells, rh)
    # the header row is the one holding the reader's header cells
    header = None
    body = []
    for r in rows:
        if header is None and any(it["role"] == "head" for it in r):
            header = r
        else:
            body.append(r)
    def by_column(r):
        out = [""] * len(cols)
        icon = band = None
        for it in sorted(r, key=lambda it: it["box"][0]):
            cx = (it["box"][0] + it["box"][2]) / 2
            ci = min(range(len(cols)), key=lambda i: 0 if cols[i][0] - rh <= cx <= cols[i][1] + rh else abs(cx - (cols[i][0] + cols[i][1]) / 2))
            text = it["text"] if it["ok"] else f"*{it['text']}*"
            if out[ci] and alike_readings(out[ci], it["text"]):
                if it["ok"] or (out[ci].startswith("*") and len(it["text"]) > len(out[ci]) - 2):
                    out[ci] = text if it["ok"] or out[ci].startswith("*") else out[ci]
            else:
                out[ci] = (out[ci] + " " + text).strip()
            icon = icon or it.get("icon")
            band = band or it.get("band")
        return out, icon, band
    head_cells = by_column(header)[0] if header else [""] * len(cols)
    body_rows = [by_column(r) for r in body]
    # the reader takes the first file for the header when the real headings
    # sit above its block: a header with none of Finder's words and a
    # file-like first cell is a row
    if header and not any(split_heads(h) for h in head_cells if h) and head_cells[0] and (
            "." in head_cells[0] or re.search(r"\d{4}", " ".join(head_cells))):
        body_rows.insert(0, by_column(header))
        head_cells = [""] * len(cols)
        header = None
    # the list goes on above the reader's block: leftover rows whose words
    # sit in the columns are rows; the row of headings is the header and
    # ends the climb; what is left above stays above
    rest_top = []
    first_y = y_lo
    climbing = True
    for r in reversed(table_rows(sorted(top, key=lambda it: it["box"][1]), rh)):
        r = sorted(r, key=lambda it: it["box"][0])
        ry1 = max(it["box"][3] for it in r)
        if climbing and first_y - ry1 <= 3 * rh and any(split_heads(it["text"]) for it in r) and not any(head_cells):
            placed = [it for it in r if split_heads(it["text"]) and it["box"][0] >= x_lo - rh]
            if placed:
                head_cells = by_column(placed)[0]
                first_y = min(it["box"][1] for it in placed)
                rest_top.extend(it for it in r if it not in placed)
            climbing = False
            continue
        if climbing and first_y - ry1 <= 3 * rh and not any(head_cells):
            cells_ = [""] * len(cols)
            ok = True
            for it in r:
                cx = (it["box"][0] + it["box"][2]) / 2
                hit = next((i for i in range(len(cols)) if cols[i][0] - rh <= cx <= cols[i][1] + rh), None)
                if hit is None or it["box"][0] < x_lo - rh or (len(it["text"]) > 40 and it["text"].count(" ") >= 5):
                    ok = False
                    break
                text = it["text"] if it["ok"] else f"*{it['text']}*"
                cells_[hit] = (cells_[hit] + " " + text).strip()
            if ok and any(cells_):
                body_rows.insert(0, (cells_, None, None))
                first_y = min(it["box"][1] for it in r)
                continue
        climbing = False
        rest_top.extend(r)
    for it in rest_top:
        it["above"] = (first_y - it["box"][3]) / rh
    top = rest_top
    # a column with no heading and under two cells is a stray reading's
    # doing; its cells fold into the neighbour on the left (or right)
    keep = []
    for i in range(len(cols)):
        filled = sum(1 for cells_, _, _ in body_rows if cells_[i])
        if not head_cells[i] and filled < 2 and len(cols) > 1:
            j = i - 1 if i > 0 else i + 1
            for cells_, _, _ in body_rows:
                if cells_[i]:
                    cells_[j] = (cells_[j] + " " + cells_[i]).strip()
                    cells_[i] = ""
        else:
            keep.append(i)
    head_cells = [head_cells[i] for i in keep]
    body_rows = [([cells_[i] for i in keep], icon, band) for cells_, icon, band in body_rows]
    cols = [cols[i] for i in keep]
    # a column headed by a sidebar word (Recents, Favorites) is the
    # sidebar, read into the list because its heading sat level with "Name"
    side_x = None
    first_col = [cells_[0] for cells_, _, _ in body_rows if cells_[0]]
    sidebarish = sum(1 for c in first_col if any(sw == c.strip("*") or sw.startswith(c.strip("*")) for sw in SIDEBAR_WORDS))
    if head_cells and (head_cells[0] in SIDEBAR_HEADS or (head_cells[0] in SIDEBAR_WORDS and first_col and sidebarish * 2 >= len(first_col))):
        side_x = cols[0]
        side_words = [head_cells[0]] + [cells_[0] for cells_, _, _ in body_rows if cells_[0]]
        side = [{"text": w, "box": [side_x[0], y_lo + k * rh, side_x[1], y_lo + (k + 1) * rh], "ok": True, "role": "left"}
                for k, w in enumerate(side_words)] + side
        head_cells = head_cells[1:]
        body_rows = [(cells_[1:], icon, band) for cells_, icon, band in body_rows if any(cells_[1:])]
        cols = cols[1:]
        x_lo = cols[0][0] if cols else x_lo
    # the list goes on below the reader's block: a leftover row whose words
    # sit in the columns is a row; a row of crumbs is the path bar; a word in
    # the sidebar's strip is the sidebar's; a sentence is the window behind
    rest = []
    last_y = y_hi
    below_rows = [sorted(r, key=lambda it: it["box"][0]) for r in table_rows(sorted(bottom, key=lambda it: it["box"][1]), rh)]
    below_rows = [[it for it in r if it["box"][0] <= x_hi + 3 * rh] for r in below_rows]
    below_rows = [r for r in below_rows if r]     # another window's words, right of this one
    last_wide = max((i for i, r in enumerate(below_rows) if len(r) >= 2), default=-1)
    for bi, r in enumerate(below_rows):
        ry0 = min(it["box"][1] for it in r)
        crumbs = sum(1 for it in r if crumb_like(it["text"]) or it["text"].endswith(">"))
        if crumbs >= 2 and crumbs >= len(r) - 1 and not rest and bi >= last_wide:
            rest.extend(r)        # the path bar: the list ends above it
            continue
        if side_x and all(it["box"][2] <= side_x[1] + rh for it in r):
            side.extend(r)
            continue
        if all(it["text"] in SIDEBAR_WORDS or it["text"].endswith(">") for it in r):
            rest.extend(r)        # a crumb or a sidebar word alone: not a row
            continue
        if ry0 - last_y > 3 * rh or rest:
            rest.extend(r)
            continue
        cells_ = [""] * len(cols)
        placed = True
        for it in r:
            if side_x and it["box"][2] <= side_x[1] + rh:
                side.append(it)
                continue
            cx = (it["box"][0] + it["box"][2]) / 2
            hit = next((i for i in range(len(cols)) if cols[i][0] - rh <= cx <= cols[i][1] + rh), None)
            wide = hit is not None and it["box"][2] > cols[hit][1] + (cols[hit + 1][0] - cols[hit][1]) / 2 if hit is not None and hit + 1 < len(cols) else False
            if hit is None or it["box"][0] < x_lo - rh or wide or (len(it["text"]) > 40 and it["text"].count(" ") >= 5):
                placed = False
                break
            text = it["text"] if it["ok"] else f"*{it['text']}*"
            cells_[hit] = (cells_[hit] + " " + text).strip()
        if placed and any(cells_) and not (len(r) == 1 and not r[0]["ok"]):
            body_rows.append((cells_, None, None))
            last_y = max(it["box"][3] for it in r)
        else:
            rest.extend(r)
    bottom = rest
    span = [min(c[0] for c in cols), max(c[1] for c in cols)] if cols else None
    if side:
        span[0] = min(span[0], min(it["box"][0] for it in side))
    return top, side, head_cells, body_rows, bottom, doubts, span, rh


SIDEBAR_HEADS = {"Recents", "Shared", "Favorites", "Locations", "Tags", "iCloud", "AirDrop"}
SIDEBAR_WORDS = SIDEBAR_HEADS | {"iCloud Drive", "Applications", "Desktop", "Documents", "Downloads", "Pictures",
                                 "Movies", "Music", "Home", "Network", "Macintosh HD", "Recents"}


def table_from_loose(pane):
    """A list the reader left loose, rebuilt from the words' positions when
    its column headings (Name, Date Modified, Size, Kind) sit on one row:
    columns start where the headings start, rows are the word rows below,
    a word left of the first column is the sidebar, above is the toolbar,
    a row of crumbs below is the path. Same return shape as build_table."""
    return table_from_items(items_of(pane))


def _bare(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _alike(a, b):
    """Two readings of the same word: most of their letters in common."""
    fa, fb = _bare(a), _bare(b)
    if not fa or not fb:
        return False
    if fa == fb:
        return True
    if min(len(fa), len(fb)) < 5:
        return False
    return difflib.SequenceMatcher(None, fa, fb, autojunk=False).ratio() >= 0.7


def table_from_items(items):
    if not items:
        return None
    rows = reading_order(items, lambda it: it["box"])
    head_row = None
    for r in rows:
        heads = [h for it in r for h in split_heads(it["text"])]
        if len(heads) >= 2 or (len(heads) == 1 and heads[0] == "Name"):
            head_row = r
            break
    if head_row is None:
        return None
    lone = len([h for it in head_row for h in split_heads(it["text"])]) == 1
    rh = sorted(it["box"][3] - it["box"][1] for it in items)[len(items) // 2] or 20
    hy = (head_row[0]["box"][1] + head_row[0]["box"][3]) / 2
    # the headings, in order; a reading that ran two headings together
    # ("Name Date Modified") is split, each part's column starting where
    # the next cluster of words below begins
    heads = []
    for it in sorted(head_row, key=lambda it: it["box"][0]):
        names = split_heads(it["text"])
        if not names:
            continue
        if len(names) == 1:
            heads.append((names[0], it["box"][0], it["box"][2]))
            continue
        nxt = next((j["box"][0] for j in sorted(head_row, key=lambda j: j["box"][0]) if j["box"][0] > it["box"][2]), float("inf"))
        crumb_rows = [r for r in rows if len(r) >= 2 and all(crumb_like(j["text"]) or j["text"].endswith(">") for j in r)
                      and (r[0]["box"][1] + r[0]["box"][3]) / 2 > hy + 3 * rh]
        skip = {id(j) for r in crumb_rows for j in r}
        xs = sorted(j["box"][0] for j in items
                    if j not in head_row and id(j) not in skip and it["box"][0] - rh <= j["box"][0] < nxt - rh
                    and j["box"][1] > hy and not (len(j["text"]) > 40 and j["text"].count(" ") >= 5))
        below = []                    # each cluster of left edges, by its leftmost
        for x in xs:
            if below and x - below[-1][-1] <= 1.5 * rh:
                below[-1].append(x)
            else:
                below.append([x])
        below = [min(c) for c in below]
        for k, name in enumerate(names):
            if k < len(below):
                x0 = below[k] if k else it["box"][0]
                x1 = (below[k + 1] - rh) if k + 1 < len(below) else it["box"][2]
                heads.append((name, x0, max(x1, x0 + rh)))
    if not heads:
        return None
    cols = [[x0, x1] for _, x0, x1 in heads]
    x_lo = cols[0][0]
    x_end = cols[-1][1] + 3 * rh         # beyond the last heading's reach: another window
    top, side, body, bottom = [], [], [], []
    def listy(r):
        return sum(1 for it in r if it["box"][2] > x_lo - rh and it["box"][0] <= x_end) >= 2
    last_listy = max((i for i, r in enumerate(rows) if listy(r)), default=-1)
    def sidebar_word(it):
        t = it["text"]
        return len(t) <= 18 and t.count(" ") <= 1 and not t.endswith((".", ",")) and ".md" not in t
    for ri, r in enumerate(rows):
        if r is head_row:
            side.extend(it for it in r if it["box"][2] <= x_lo - rh and sidebar_word(it))   # "Recents", level with "Name"
            continue
        cy = (r[0]["box"][1] + r[0]["box"][3]) / 2
        if cy < hy - rh:
            for it in r:
                it["above"] = (hy - cy) / rh
            top.extend(r)
            continue
        # the path bar: a row of crumbs with no list row under it
        if (len(r) >= 2 and all(crumb_like(it["text"]) or it["text"].endswith(">") for it in r) and cy > hy + 3 * rh
                and ri >= last_listy):
            bottom.extend(it for it in r if it["box"][2] > x_lo - rh and it["box"][0] <= x_end)
            side.extend(it for it in r if it["box"][2] <= x_lo - rh and sidebar_word(it))   # the sidebar's last entry, level with the path bar
            continue
        in_list = [it for it in r if it["box"][2] > x_lo - rh and it["box"][0] <= x_end
                   and not (len(it["text"]) > 40 and it["text"].count(" ") >= 5)]
        if len(in_list) == 1 and not in_list[0]["ok"]:
            # A lone doubtful word is not a row - UNLESS it stands exactly
            # where a row's first cell stands. A word aligned to the Name
            # column, down in the body of the list, is a row the engines
            # read only once: dropped, the list lost the very folder being
            # opened and the row standing selected in it. Kept, it is
            # marked unsure like every other one-engine reading here.
            if abs(in_list[0]["box"][0] - x_lo) > 0.6 * rh:
                continue
        left = [it for it in r if it["box"][2] <= x_lo - rh]
        side.extend(it for it in left if sidebar_word(it))
        if not in_list:
            continue
        if all(crumb_like(it["text"]) for it in in_list) and len(in_list) >= 2 and cy > hy + 3 * rh and ri >= last_listy:
            bottom.extend(in_list)
            continue
        cells = [""] * len(cols)
        icon = band = None
        for it in in_list:
            cx = it["box"][0]
            ci = max((i for i in range(len(cols)) if cols[i][0] - rh <= cx), default=0)
            text = it["text"] if it["ok"] else f"*{it['text']}*"
            # TWO READINGS OF ONE CELL ARE NOT TWO THINGS IN IT. Where the
            # engines both put a word in the same column of the same row and
            # the two read alike, the fuller of them stands; strung together
            # the cell says the file was called both, one after the other.
            if cells[ci] and _alike(cells[ci], text):
                if len(_bare(text)) > len(_bare(cells[ci])):
                    cells[ci] = text
            else:
                cells[ci] = (cells[ci] + " " + text).strip()
            icon = icon or it.get("icon")
            band = band or it.get("band")
        if any(cells):
            body.append((cells, icon, band))
    if len(body) < (4 if lone else 2):
        return None
    head = [name for name, _, _ in heads]
    span = [min([x_lo] + [it["box"][0] for it in side]), cols[-1][1]]
    return top, side, head, body, bottom, [], span, rh


def split_heads(text):
    """The Finder headings a reading holds, in order: "Name" -> ["Name"],
    "Name Date Modified" -> ["Name", "Date Modified"], anything else -> []."""
    words = text.split()
    out = []
    i = 0
    while i < len(words):
        hit = None
        for n in (2, 1):
            cand = " ".join(words[i:i + n])
            if cand in FINDER_HEADS:
                hit = (cand, n)
                break
        if not hit:
            return []
        out.append(hit[0])
        i += hit[1]
    return out


FINDER_HEADS = {"Name", "Date Modified", "Size", "Kind", "Date Created", "Date Added"}


# ------------------------------------------------------------- pane blocks, as markdown

ICON = {"green": '<span class="sn-ico"></span>', "grey": '<span class="sn-ico grey"></span>',
        "white": '<span class="sn-ico file"></span>'}


def md_table(head, rows):
    n = max([len(head)] + [len(r[0]) for r in rows]) if rows or head else 0
    if n == 0:
        return []
    head = list(head) + [""] * (n - len(head))
    out = ["| " + " | ".join(cell(h) for h in head) + " |",
           "|" + "---|" * n]
    for cells, icon, band in rows:
        cells = list(cells) + [""] * (n - len(cells))
        cells = [cell(c) for c in cells]
        # no icon boxes in cells: they collide with the names, and the Kind
        # column already says folder or file
        if band:
            cells = [f"**{c}**" if c else c for c in cells]
        out.append("| " + " | ".join(cells) + " |")
    return out


def words_line(items):
    """Loose items as lines of words in reading order."""
    return [" &nbsp; ".join(it["text"] for it in r) for r in reading_order(items, lambda it: it["box"])]


def block_list(pane):
    built = build_table(pane)
    lines, doubts = [], []
    if not built:
        return lines, doubts
    top, side, head, rows, bottom, doubts = built[:6]
    def say(it):
        return it["text"] if it["ok"] else f"*{it['text']}*"
    if top:
        lines.append("**Toolbar:** " + " · ".join(say(it) for it in sorted(top, key=lambda it: it["box"][0])))
    if side:
        lines.append("**Sidebar:** " + " · ".join(say(it) for it in sorted(side, key=lambda it: it["box"][1])))
    if top or side:
        lines.append("")
    lines.extend(md_table(head, rows))
    if bottom:
        items = sorted(bottom, key=lambda it: (round(it["box"][1] / 10), it["box"][0]))
        crumbs = [say(it).rstrip(">").strip() for it in items if crumb_like(it["text"])]
        words = [say(it) for it in items if not crumb_like(it["text"])]
        if len(crumbs) >= 2:
            lines.append("")
            lines.append("**Path:** " + " › ".join(crumbs))
            pane["_path_end"] = crumbs[-1].strip("*")
        if words:
            lines.append("")
            lines.append(" · ".join(words))
    return lines, doubts


def block_tree(pane):
    d = pane.get("data") or {}
    rows = d.get("rows") or []
    lines, doubts = ["```text"], []
    for r in rows:
        ch = {"right": "▸ ", "down": "▾ "}.get(r.get("chevron"), "  ")
        name = r.get("name") or r.get("raw") or ""
        lines.append("  " * int(r.get("depth", 0)) + ch + name)
        if r.get("name_status") == "uncertain" and r.get("name_second"):
            doubts.append(f"{name} / {r['name_second']}")
    lines.append("```")
    if not rows:
        lines = []
    return lines, doubts


def block_document(pane):
    lines, doubts, props = [], [], []
    in_props = False
    for raw in pane.get("lines") or []:
        s = raw.strip()
        if s.startswith(("[also on this pane", "unsettled:", "[dark look", "[light look")):
            if s.startswith("unsettled:"):
                doubts.append(s[len("unsettled:"):].strip())
            continue
        text, notes = strip_note(raw)
        for n in notes:
            if n.startswith("drawn in ") and n[len("drawn in "):] in old.HUES:
                # the colour was measured for the whole line, and a line is
                # rarely coloured whole; it is said rather than painted
                doubts.append(f"{text.strip()[:30]}: something on this line "
                              f"was drawn in {n[len('drawn in '):]}")
            elif n.startswith("the line runs on past the edge"):
                text = text.rstrip() + "…"
            else:
                doubts.append(f"{text.strip()[:30]}: {n}")
        if text.strip() == "---":
            if in_props:
                lines.append("**Properties:** " + " · ".join(props))
                lines.append("")
                props = []
            in_props = not in_props
            continue
        if in_props:
            props.append(text.strip())
            continue
        indent = len(text) - len(text.lstrip(" "))
        body = text.strip()
        if not body:
            continue
        pad = "&nbsp;" * min(8, indent)
        lines.append(pad + body if indent >= 4 and not body.startswith(("#", "-", "*")) else body)
    return lines, doubts


def block_lines(pane):
    """A terminal or chat: its lines in a code block."""
    lines = [ln for ln in old.content_lines(pane) if ln.strip()]
    return (["```text"] + [ln.rstrip() for ln in lines] + ["```"]) if lines else [], []


def block_loose(pane, window_rect):
    """Loose words: a narrow strip is a sidebar line, a short strip along the
    top a toolbar line, anything else lines of words in reading order."""
    items = [it for it in items_of(pane) if it["ok"]]
    doubts = [it["text"] for it in items_of(pane) if not it["ok"]]
    if not items:
        return [], doubts
    x0, y0, x1, y1 = pane["box"]
    W = max(1, window_rect[2] - window_rect[0])
    H = max(1, window_rect[3] - window_rect[1])
    w, h = x1 - x0, y1 - y0
    texts_in_order = [it["text"] for r in reading_order(items, lambda it: it["box"]) for it in r]
    if w < 0.3 * W and h > w:
        label = "Sidebar" if (x0 - window_rect[0]) < 0.5 * W else "Right panel"
        return [f"**{label}:** " + " · ".join(texts_in_order)], doubts
    if h < 0.12 * H and y0 < window_rect[1] + 0.1 * H:
        return ["**Toolbar:** " + " · ".join(texts_in_order)], doubts
    return words_line(items), doubts


def _finder_sizes(pane):
    """A run of byte counts down one column: Finder's Size column, still
    recognisable when the headings are off the side of the screen."""
    n = 0
    for it in items_of(pane):
        t = str(it.get("text", "")).replace(" ", "")
        if re.match(r"^\d+(\.\d+)?(bytes?|KB|MB|GB|TB)$", t, re.I):
            n += 1
    return n >= 3


def block_of(pane, window_rect):
    k = pane["kind"]
    # A WINDOW RUNNING OFF THE EDGE OF THE SCREEN STILL SHOWS A LIST. At
    # 00:03:00 a Finder stood cut off down the left edge with only its Size
    # and Kind columns in view; the reader could not call that a list of
    # columns, so it became loose words, the window group had no content at
    # all, no state was built - and the picture filled the rectangle from a
    # remembered Finder that had once shown the `.claude` folder. Six file
    # names the screen never showed. A run of byte counts is Finder's Size
    # column wherever it stands, which is the same test that NAMES the
    # window Finder a few lines further down.
    if k not in ("a list of columns", "a file tree", "an open document",
                 "a terminal", "a chat log") and _finder_sizes(pane):
        got = block_list(pane)
        if got and got[0]:
            return got
    if k == "a list of columns":
        return block_list(pane)
    if k == "a file tree":
        return block_tree(pane)
    if k == "an open document":
        return block_document(pane)
    if k in ("a terminal", "a chat log"):
        return block_lines(pane)
    return block_loose(pane, window_rect)


# ------------------------------------------------------------- windows and moments

SIDE_NAMES = {
    "recents", "shared", "airdrop", "favorites", "applications", "pictures",
    "movies", "music", "desktop", "documents", "downloads", "locations",
    "icloud drive", "icloud", "network", "tags", "home", "library",
}


def finder_sidebar(pane):
    """A Finder window's own sidebar, read as though it were a file tree.

    Down the left of every Finder window stands a fixed list - Recents,
    Shared, Applications, Pictures, and the rest - and read on its own,
    with the window's list hidden behind whatever stands in front, it has
    the shape of a tree. Called a tree, it names the window Obsidian, and
    a Finder window comes out labelled for the wrong program.
    """
    rows = [str(r.get("name") or "").strip().lower()
            for r in ((pane.get("data") or {}).get("rows") or [])]
    rows = [r for r in rows if r]
    if len(rows) < 4:
        return False
    return sum(1 for r in rows if r in SIDE_NAMES) >= max(3, 0.6 * len(rows))


def name_of(entry, panes):
    """The program, from its furniture; a list under Finder's own column
    headings is Finder even with its sidebar out of view."""
    app = old.app_name(entry, panes)

    def finder_columns(p):
        """A list standing under Finder's own column headings."""
        if p["kind"] != "a list of columns":
            return False
        d = p.get("data") or {}
        heads = {h for b in d.get("blocks") or [] for h in (b.get("header") or [])}
        heads |= {r["text"] for r in d.get("remainder") or []
                  if r.get("where") in ("above", "beside")}
        return len(heads & FINDER_HEADS) >= 2

    # Finder's own furniture is asked about FIRST. A window's list read
    # with only its Name column showing - the rest off the side of the
    # screen or behind another window - comes back as a file tree, and a
    # tree taken as the deciding word names a Finder window Obsidian even
    # while its column headings stand in the pane beside it.
    def finder_bar(p):
        """A path bar: the disk, then the folders down to this one. No
        other program draws that, and it is the one piece of furniture a
        Finder window keeps however little of it is showing."""
        w = old.pane_words(p) or ""
        flat = w.replace(" ", "")
        if ("MacintoshHD>" in flat or "MacintoshHD›" in flat
                or ("Users>" in flat and flat.count(">") >= 2)):
            return True
        # the same bar read crumb by crumb: each folder comes back as its
        # own word and the chevrons between them fall out, so the run of
        # them is all that is left to recognise
        return "MacintoshHD" in flat and "Users" in flat

    def finder_sizes(p):
        """Finder's Size column: a run of byte counts down one column.
        No document prints that, and it is still there when the column
        headings are off the side of the screen or behind another window."""
        n = 0
        for it in items_of(p):
            t = str(it.get("text", "")).replace(" ", "")
            if re.match(r"^\d+(\.\d+)?(bytes?|KB|MB|GB|TB)$", t, re.I):
                n += 1
        return n >= 3

    if any(finder_columns(p) or finder_bar(p) or finder_sizes(p) for p in panes):
        app = "Finder"
    elif any(finder_sidebar(p) for p in panes):
        app = app or "Finder"   # its sidebar is the one thing still in view
    elif any(p["kind"] == "a file tree" for p in panes):
        app = "Obsidian"        # a file tree is the vault's; a browser shows none
    elif app in (None, "the browser"):
        # a note with a properties panel is Obsidian's, whatever tab strip
        # shows behind it
        for p in panes:
            if p["kind"] != "an open document":
                continue
            d = p.get("data") or {}
            words = " ".join(r.get("text", "") for r in d.get("remainder") or []) + " " + old.pane_words(p)
            if d.get("properties") or "Properties" in words or "Add property" in words:
                app = "Obsidian"
                break
    if not app:
        for p in panes:
            if p["kind"] == "a list of columns":
                d = p.get("data") or {}
                heads = {h for b in d.get("blocks") or [] for h in (b.get("header") or [])}
                heads |= {r["text"] for r in d.get("remainder") or [] if r.get("where") in ("above", "beside")}
                if len(heads & FINDER_HEADS) >= 2:
                    app = "Finder"
    return (app[0].upper() + app[1:]) if app else None


def touching(a, b, W):
    """Two pane boxes that share an edge, left-right or top-bottom."""
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    gap = 0.02 * W
    side = (abs(ax1 - bx0) < gap or abs(bx1 - ax0) < gap) and min(ay1, by1) - max(ay0, by0) > 0
    stack = (abs(ay1 - by0) < gap or abs(by1 - ay0) < gap) and min(ax1, bx1) - max(ax0, bx0) > 0
    return side or stack


GENERIC = "A window"        # what a window is called when nothing names it


def _fold_split(m, groups):
    """Fold each window the frame closed twice back into one group."""
    import cv2                     # only a desktop with two windows on it
    import panes as _panes         # needs the frame's own pixels
    try:
        img = cv2.imread(shapes.frame_of(m))
    except Exception:
        img = None
    if img is None:
        return groups
    try:
        pairs = _panes.split_pairs(img, [g["rect"] for g in groups])
    except Exception:
        return groups
    for i, j in pairs:
        a, b = groups[i], groups[j]
        r, o = list(a["rect"]), list(b["rect"])
        a["rect"] = [min(r[0], o[0]), min(r[1], o[1]),
                     max(r[2], o[2]), max(r[3], o[3])]
        a["panes"] = a["panes"] + b["panes"]
        # the whole side carries the buttons; the FOLDER'S NAME sits in the
        # toolbar over the pane, so the title is whichever half has one
        # NAMING IS NOT RE-RUN ON THE JOINED PANES, and that is the point of
        # doing this here rather than after. A Finder's sidebar reads as a
        # file tree and its list reads as text, so the two together read as
        # a tree beside a note - the shape of Obsidian. Asked again, the
        # window came back named for the wrong program, collided with the
        # real Obsidian window and was dropped: at 00:00:10 the vault-demo
        # Finder vanished from the picture and from the record's own count
        # of how many windows the screen showed. Each half was already named
        # while it still looked like what it is; the name to keep is the one
        # from the half that carried the folder's name.
        # THE NAME IS THE ONE THAT IS ACTUALLY A NAME. Each half was named
        # from what it alone holds, and only one half can be: the sidebar
        # side reads as a Finder, while the file list on its own is just
        # text and falls back to the bare "A window". Taking the titled
        # half's name because it carried the folder's name kept exactly the
        # wrong one, and a window called "A window" is not shown at all -
        # the vault-demo Finder left the picture entirely.
        if a["name"] == GENERIC and b["name"] != GENERIC:
            a["name"] = b["name"]
        a["title"] = a.get("title") or b.get("title")
        # AND THE RECORD'S OWN ENTRIES MOVE WITH IT. The box a window is
        # drawn at is looked up later from the reader's entry for it, by the
        # number its panes carry - so leaving the entries at their halves
        # drew the joined window at the width of its sidebar alone. Both
        # entries take the joined rectangle, so whichever number the panes
        # answer with, the box is the same one.
        for e_ in m.get("windows") or []:
            if e_.get("wi") in (a.get("wi"), b.get("wi")):
                e_["rect"] = list(a["rect"])
        # HOW WIDE THE SIDEBAR REALLY WAS. The card draws one at a fixed
        # width, which is right for a Finder of ordinary size and wrong for
        # this one: on the frame the sidebar takes a little over half the
        # window, so a drawing that gives it a fifth puts every row of the
        # file list left of where the screen had it. The split is the one
        # thing this fold knows exactly - it is the seam it just measured.
        whole = max(1.0, a["rect"][2] - a["rect"][0])
        a["side_share"] = max(0.12, min(0.7, (r[2] - a["rect"][0]) / whole))
        b["folded"] = True
    return [g for g in groups if not g.get("folded")]


def window_groups(m):
    """The windows of a moment: (name, rect, panes). Panes on no found
    window form one group of their own."""
    wins = m.get("windows") or []
    groups = []
    for pos, e in enumerate(wins):
        # a window's entry carries its OWN number, and the list is written
        # in screen order, not in that number's order. Counting positions
        # here hands one window another window's panes the moment the two
        # orders differ -- a window named for the program standing beside it.
        wi = e.get("wi", pos)
        panes = [p for p in m["panes"] if p.get("wi") == wi]
        if not panes:
            continue
        name = name_of(e, panes) or GENERIC
        title = e.get("top")
        groups.append({"name": name, "title": title, "rect": e["rect"], "panes": panes,
                       "where": e.get("where"), "wi": wi})
    # ONE WINDOW THE FRAME CLOSED TWICE - once whole, once at its own
    # sidebar divider - is one window, and its panes are all its own. Left
    # apart, the drawing gave each half a title bar and a set of traffic
    # lights: at 00:00:10 the note showed two `vault-demo` windows where the
    # screen had one, the sidebar in the first and the file list in the
    # second. The two measurements that tell this from two windows genuinely
    # standing side by side live in `panes.fold_split_panes`.
    if len(groups) > 1:
        groups = _fold_split(m, groups)
    rest = [p for p in m["panes"] if p.get("wi") is None or p.get("wi") >= len(wins)]
    # A window's path bar sits at its foot, and its foot can fall a little
    # below the rectangle the frame measured - on a frame caught mid-scroll
    # it always does. The pane holding it is then filed under no window at
    # all, and the window loses the one piece of furniture that says beyond
    # doubt which program it is. A leftover pane standing at a window's own
    # width, right against its top or its foot, belongs to that window.
    if rest and groups:
        still = []
        for p in rest:
            b = p["box"]
            for g in groups:
                r = g["rect"]
                wide = max(1.0, r[2] - r[0])
                if abs(b[0] - r[0]) > 0.06 * wide or abs(b[2] - r[2]) > 0.06 * wide:
                    continue
                gap = 0.06 * max(1.0, r[3] - r[1])
                if -gap <= b[1] - r[3] <= gap or -gap <= r[1] - b[3] <= gap:
                    g["panes"].append(p)
                    g["rect"] = [min(r[0], b[0]), min(r[1], b[1]),
                                 max(r[2], b[2]), max(r[3], b[3])]
                    g["grew"] = True
                    break
            else:
                still.append(p)
        rest = still
        # named again, now the window has all of its furniture: the bar it
        # just gained is the one thing that says beyond doubt what program
        # this window belongs to
        for g in groups:
            if g.pop("grew", False):
                e = {"rect": g["rect"], "top": g.get("title")}
                g["name"] = name_of(e, g["panes"]) or g["name"]
    size = list(m.get("size") or [1920, 1080])
    if rest and groups:
        groups.append({"name": "The rest of the screen", "title": None, "rect": [0, 0] + size,
                       "panes": rest, "where": None})
    elif rest:
        # no window was found: each structural pane is a window of its own,
        # with any narrow loose strip beside it as its sidebar; loose panes
        # left over stand alone
        W = size[0]
        # The windows the screen itself drew. Panes on opposite sides of a
        # window's own edge are panes of DIFFERENT windows, and joining
        # them makes one window out of two: a Finder list beside another
        # Finder's sidebar reads as a tree next to a list, which is the
        # shape of Obsidian, and the window comes out named for the wrong
        # program with the wrong content in it.
        drawn_wins = []
        try:
            got = shapes.find(shapes.frame_of(m))
            got.sort(key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
            for r in got:
                if not any(min(r[2], k[2]) - max(r[0], k[0]) > 0.85 * (r[2] - r[0])
                           and min(r[3], k[3]) - max(r[1], k[1]) > 0.85 * (r[3] - r[1])
                           for k in drawn_wins):
                    drawn_wins.append(r)
        except Exception:
            drawn_wins = []

        def whose(p):
            """Which drawn window this pane's middle stands in, or None."""
            cx = (p["box"][0] + p["box"][2]) / 2
            cy = (p["box"][1] + p["box"][3]) / 2
            for i, r in enumerate(drawn_wins):
                if r[0] <= cx <= r[2] and r[1] <= cy <= r[3]:
                    return i
            return None

        structural = [p for p in rest if p["kind"] in old.STRUCTURAL]
        loose = [p for p in rest if p["kind"] not in old.STRUCTURAL]
        taken = set()
        # panes that touch, directly or through a narrow strip between them,
        # are one window (a tree, the panel beside it, and the note)
        def narrow(p):
            return (p["box"][2] - p["box"][0]) < 0.3 * W
        clusters = []
        for sp in sorted(structural, key=lambda p: p["box"][0]):
            if id(sp) in taken:
                continue
            members = [sp]
            grew = True
            while grew:
                grew = False
                for q in rest:
                    if q is sp or id(q) in taken or q in members:
                        continue
                    if q["kind"] not in old.STRUCTURAL and not narrow(q):
                        continue
                    if q["kind"] == "a list of columns" and any(r["kind"] == "a list of columns" for r in members):
                        continue      # two lists are two windows, one behind the other
                    qw = whose(q)
                    if qw is not None and any(whose(r) is not None and whose(r) != qw
                                              for r in members):
                        continue      # the screen drew a window edge between them
                    # two panes that name DIFFERENT programs are two windows:
                    # a note with its properties panel showing in the gap
                    # beside a file list is Obsidian standing behind Finder,
                    # not one window that is somehow both
                    e0 = {"rect": [0, 0] + size, "top": None}
                    # THE BROWSER IS A STRIP ABOVE, NOT A PROGRAM BESIDE.
                    # Its chrome - the tab titles and the address bar - runs
                    # across the TOP of the screen, so those words land in
                    # the top of whatever pane happens to be leftmost. Taken
                    # as that pane's program they split one maximised window
                    # into two, and the half called "the browser" is never
                    # drawn: at 00:04:40 the Obsidian window lost its whole
                    # file-tree column that way, on a frame where the screen
                    # drew no window edges to say otherwise.
                    def _prog(pane_):
                        n_ = name_of(e0, [pane_])
                        return None if n_ == "The browser" else n_
                    qn = _prog(q)
                    if qn:
                        mine_ = [_prog(r) for r in members]
                        if any(n and n != qn for n in mine_):
                            continue
                    if any(touching(q["box"], r["box"], W) for r in members):
                        members.append(q)
                        grew = True
            for q in members:
                taken.add(id(q))      # claimed: not available to the next cluster
            clusters.append(members)
        for members in clusters:
            sp = members[0]
            e = {"rect": [0, 0] + size, "top": None}
            name = name_of(e, members) or f"A window, {sp.get('where') or 'on the screen'}"
            x0 = min(p["box"][0] for p in members); x1 = max(p["box"][2] for p in members)
            y0 = min(p["box"][1] for p in members); y1 = max(p["box"][3] for p in members)
            groups.append({"name": name, "title": None, "rect": [x0, y0, x1, y1], "panes": members, "where": sp.get("where")})
        for lp in loose:
            if id(lp) in taken or any(lp in c for c in clusters):
                continue
            e = {"rect": [0, 0] + size, "top": None}
            name = name_of(e, [lp]) or f"Loose words, {lp.get('where') or 'on the screen'}"
            groups.append({"name": name, "title": None, "rect": lp["box"], "panes": [lp], "where": lp.get("where")})
    groups.sort(key=lambda g: g["rect"][0])
    return groups


def draw_group(g):
    """One callout: the window's name as its title, its content inside."""
    rect = g["rect"]
    title = g["name"] + (f" - {g['title']}" if g.get("title") else "")
    body, doubts, repeats = [], [], []
    panes = sorted(g["panes"], key=lambda p: (p["box"][0], p["box"][1]))
    for p in panes:
        if p.get("since"):
            repeats.append(f"{p.get('where') or 'a pane'}: unchanged since {p['since']}")
            continue
        if p.get("same_as"):
            repeats.append(f"{p.get('where') or 'a pane'}: the same as at {p['same_as']}")
            continue
        lines, d = block_of(p, rect)
        doubts.extend(d)
        if lines:
            if body:
                body.append("")
            body.extend(lines)
    for r in repeats:
        body.append("")
        body.append(f"*{r}*")
    if not body:
        return [], doubts
    if not g.get("title"):
        # a Finder window is told by the folder its path ends in
        end = next((p.get("_path_end") for p in panes if p.get("_path_end")), None)
        if end:
            title = f"{g['name']} - {end}"
            g["title"] = end
    out = [f"> [!window] {title}"]
    for ln in body:
        out.append("> " + ln if ln else ">")
    return out, doubts


def said_lines(m):
    said = (m.get("said") or "").strip()
    if not said:
        return []
    if len(said) > LONG_SAID:
        return [f"> [!quote]- Jared, {m['ts']} ({len(said.split())} words)", "> " + said]
    return [f'Jared, {m["ts"]}: "{said}"']


SAME = 0.9


def flat(lines):
    text = re.sub(r"&[a-z]+;|<[^>]+>", " ", " ".join(lines))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def alike(a, b):
    """1.0 when every line of one drawing has a near twin in the other (a
    letter wobble is a twin; a new line or a vanished one is not)."""
    def norm(lines):
        out = []
        for ln in lines:
            if "unchanged since" in ln or "the same as at" in ln or ln.startswith("> [!"):
                continue          # the drawing's own markers, not the screen
            f = flat([ln])
            if f:
                out.append(f)
        return out
    A, B = norm(a), norm(b)
    if not A or not B:
        return 0.0
    def covered(xs, ys):
        scraps = 0
        whole = "".join(ys)
        # a line, or a join of up to three neighbouring lines: the same
        # text split differently between two readings
        joins = list(ys) + ["".join(ys[i:i + 2]) for i in range(len(ys) - 1)] \
            + ["".join(ys[i:i + 3]) for i in range(len(ys) - 2)]
        for x in xs:
            if len(x) >= 6 and x in whole:
                continue
            best = max((difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() for y in joins
                        if abs(len(x) - len(y)) <= max(4, 0.3 * len(x))), default=0.0)
            if best < 0.8:
                # a short scrap with no twin is the engines' noise; a real
                # line with no twin is a change on the screen
                if len(x) < 16 and scraps < 2:
                    scraps += 1
                    continue
                return False
        return True
    return 1.0 if covered(A, B) and covered(B, A) else 0.0


def group_key(g, W):
    """A window's identity across moments: its name and where it stands."""
    return f"{g['name']}@{int(8 * g['rect'][0] / max(1, W))}"


def draw_moment(m, prev_clock, prev_groups=None):
    groups = window_groups(m)
    names = " · ".join(g["name"] + (f" ({g['title']})" if g.get("title") else "") for g in groups)
    all_repeat = all(p.get("since") or p.get("same_as") for p in m["panes"]) and m["panes"]
    clock = None
    for p in m["panes"]:
        c = old.clock_in(p)
        if c:
            clock = c
    head = f"## {m['ts']} - {names or 'nothing readable'}"
    if all_repeat:
        since = sorted({p.get("since") or p.get("same_as") for p in m["panes"]})
        out = [head + f" - the same screen as at {', '.join(since)}"]
        out.extend(said_lines(m))
        return out, clock, prev_groups
    out = [head]
    doubts = []
    drawn = {}
    W = (m.get("size") or [1920])[0]
    for g in groups:
        lines, d = draw_group(g)
        g["ts"] = m["ts"]
        key = group_key(g, W)
        drawn[key] = (lines, g)
        # the same window drawn the same way a moment ago: one line back.
        # The reader's own word (every pane unchanged or read the same)
        # settles it; otherwise the drawings are compared line by line
        before = (prev_groups or {}).get(key)
        reader_says = all(p.get("since") or p.get("same_as") for p in g["panes"])
        if before and lines and before[0] and (reader_says or alike(lines, before[0]) >= SAME):
            drawn[key] = before      # the earlier drawing stands as the reference
            out.append("")
            out.append(f"> [!window] {g['name']} - the same as at {before[1].get('ts', '?')}")
            continue
        doubts.extend(d)
        if lines:
            out.append("")
            out.extend(lines)
    out.append("")
    out.extend(said_lines(m))
    small = []
    if clock and clock != prev_clock:
        small.append(f"the clock reads {clock}")
    if doubts:
        seen, kept = set(), []
        for d in doubts:
            d = re.sub(r"\s+", " ", d).strip()
            if d and d not in seen:
                seen.add(d)
                kept.append(d)
        more = f" and {len(kept) - MAX_DOUBT} more" if len(kept) > MAX_DOUBT else ""
        small.append("doubt: " + " · ".join(html.escape(x, quote=False) for x in kept[:MAX_DOUBT]) + more)
    if small:
        out.append("")
        out.append("<small>" + "; ".join(small) + "</small>")
    names = " · ".join(g["name"] + (f" ({g['title']})" if g.get("title") else "") for g in groups)
    out[0] = f"## {m['ts']} - {names or 'nothing readable'}"
    return out, clock, drawn


def note(records_path, diary_text=None):
    header, moments, footer = old.load(records_path)
    title = header.get("title") or os.path.basename(os.path.dirname(records_path))
    diary_text = diary_text if diary_text is not None else old.diary(records_path)
    secs = (moments[-1]["secs"] - moments[0]["secs"]) if len(moments) > 1 else 0
    apps = []
    for m in moments:
        for g in window_groups(m):
            n = g["name"]
            if n not in apps and not n.startswith(("The screen", "The rest of the screen", "A window", "Loose words")):
                apps.append(n)
    clocks = [c for m in moments for p in m.get("panes") or [] for c in [old.clock_in(p)] if c]
    parts = [f"# {title}", ""]
    head = f"A screen recording, {old.minutes(secs)} read, {len(moments)} screen moments in order."
    if apps:
        head += " On screen: " + "; ".join(apps) + "."
    if clocks:
        head += f" The desktop clock read {clocks[0]}" + (f" at the start and {clocks[-1]} at the end." if clocks[-1] != clocks[0] else ".")
    parts.append(head)
    parts.append("")
    prev_clock = None
    prev_groups = {}
    for m in moments:
        lines, clock, prev_groups = draw_moment(m, prev_clock, prev_groups)
        prev_clock = clock or prev_clock
        parts.extend(lines)
        parts.append("")
    n = len(moments)
    parts.append(f"> [!note]- The moment-by-moment record, {n} moments (appendix)")
    parts.append("> ````text")
    for ln in diary_text.rstrip("\n").split("\n"):
        parts.append("> " + ln if ln else ">")
    parts.append("> ````")
    return "\n".join(parts) + "\n"


def main():
    records = sys.argv[1]
    text = note(records)
    if len(sys.argv) > 2:
        out = sys.argv[2]
        tmp = out + ".tmp-write"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, out)
        print(f"{out}: {len(text)} characters")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
