#!/usr/bin/env python3
"""Read a list-and-column view: a Finder window, a table, a settings list.

A file tree carries its meaning in its indentation. A LIST carries its meaning
sideways: Name, Date Modified, Size, Kind, each value belonging to a heading
above it. Read row by row it comes back as "Assets 16 Jun 2026 -- Folder",
which is not what the screen says: it says Name=Assets, Modified=16 Jun 2026,
Size=--, Kind=Folder. Losing the pairing loses the note.

The instrument is the same shape as the tree's guide lines -- a fact about the
pixels rather than a judgment about the text:

    a column boundary is a vertical corridor of blank pixels
    that no row's text crosses, running the full height of the list

Prose has no such corridor. A word may end anywhere and the next line begins
again at the margin, so any blank column is closed by some line or other. A
column view cannot close them: the application reserves that space and clips
text that would reach it. So the corridors ARE the columns, and finding them
is a count of blank pixels, with nothing to tune and no template to learn.

The corridors give the columns. They do not give every ROW, because a table
has rows that do not share them: a heading left-aligned over right-aligned
numbers crosses the corridor its own column stands on, a selected row drawn
white on a coloured fill changes what counts as blank across it, and one long
name can run within two spaces of the next column. Once the columns are
settled, each neighbouring row is asked the simpler question -- does it fill
every column, one cell to each, with nothing left over -- and taken back if it
does. The topmost row of what results is the header; the rest pair their cells
to it by position.
"""
import statistics
import sys

import cv2
import numpy as np

import note_reader
import machine

MIN_BAND = 3          # a band narrower than this many spaces is not a column
MIN_ROWS = 3          # a table is a heading and at least two rows


def ink_columns(mask):
    """For each x, how many of the mask's rows carry ink there."""
    return mask.sum(axis=0)


def row_gaps(mask, row, space_w):
    """The blank x ranges inside one row, wider than a word space."""
    band = mask[row["y0"]:row["y1"], :]
    empty = band.sum(axis=0) == 0
    runs, start = [], None
    for x, e in enumerate(empty):
        if e and start is None:
            start = x
        elif not e and start is not None:
            runs.append((start, x))
            start = None
    if start is not None:
        runs.append((start, len(empty)))
    return [(a, b) for a, b in runs if (b - a) >= space_w * MIN_BAND]


def overlap(runs_a, runs_b):
    """What two sets of blank ranges have in common."""
    out = []
    for a0, a1 in runs_a:
        for b0, b1 in runs_b:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi > lo:
                out.append((lo, hi))
    return out


def blocks(mask, rows, space_w):
    """Find every run of rows that shares blank corridors, best runs first.

    Asking the WHOLE pane for corridors is too strict for a real window. A
    full-width rule between sections -- often drawn on the same line as the
    section's title -- lays ink clean across every corridor, and one such row
    collapses five columns into two. Nor is there one corridor set to find:
    a window can stack several tables, and a grid of cards is exactly that,
    each band with its own column positions.

    So a block is a RUN of consecutive rows whose blank ranges still overlap.
    Every run is measured, the richest are taken first -- most columns, then
    most rows -- and a row already spent on one block cannot join another.
    A plain list comes back as one block and a card grid as several, with
    neither told apart by a rule written for it.
    """
    n = len(rows)
    rows_gaps = [row_gaps(mask, r, space_w) for r in rows]
    floor = space_w * MIN_BAND
    cands = []
    for i in range(n):
        corrs = rows_gaps[i]
        for j in range(i + 1, n):
            corrs = [(a, b) for a, b in overlap(corrs, rows_gaps[j])
                     if (b - a) >= floor]
            if not corrs:
                break
            if j - i + 1 >= MIN_ROWS:
                cands.append((len(corrs) + 1, j - i + 1, i, j, corrs))
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    used, out = set(), []
    for _, _, i, j, corrs in cands:
        if any(k in used for k in range(i, j + 1)):
            continue
        used.update(range(i, j + 1))
        out.append((rows[i:j + 1], corrs))
    out.sort(key=lambda b: b[0][0]["y0"])
    return out, None


def space_width(rows):
    """How wide a space is drawn, from the gaps between words in a row.

    Taken from the text itself rather than assumed, so the zoom and the font
    fall out of the answer.
    """
    gaps = []
    for r in rows:
        words = r.get("words") or []
        for a, b in zip(words, words[1:]):
            g = b[1] - a[2]
            if 0 < g:
                gaps.append(g)
    return statistics.median(gaps) if gaps else 6.0


def bands_from(corrs, width):
    """The columns are what the corridors leave behind."""
    edges = [0]
    for a, b in corrs:
        edges.append((a + b) // 2)
    edges.append(width)
    return [(a, b) for a, b in zip(edges, edges[1:]) if b > a]


def group_rows(cells_in, ):
    """Group loose OCR cells into the visual rows they sit on.

    The cell engine returns each value as its own box, which is what a column
    view needs -- but the rows have to be put back, and a row is simply the
    cells whose vertical extents overlap.
    """
    out = []
    for c in sorted(cells_in, key=lambda c: c["y0"]):
        placed = False
        for row in out:
            mid = (c["y0"] + c["y1"]) / 2
            if row["y0"] <= mid <= row["y1"]:
                row["cells"].append(c)
                row["y0"] = min(row["y0"], c["y0"])
                row["y1"] = max(row["y1"], c["y1"])
                placed = True
                break
        if not placed:
            out.append({"y0": c["y0"], "y1": c["y1"], "cells": [c]})
    for row in out:
        row["cells"].sort(key=lambda c: c["x0"])
        row["x0"] = min(c["x0"] for c in row["cells"])
        row["x1"] = max(c["x1"] for c in row["cells"])
        row["text"] = " ".join(c["text"] for c in row["cells"])
    out.sort(key=lambda r: r["y0"])
    return out


def second_reading(row, cell, tess_words):
    """What the other engine read inside this cell's box."""
    picked = [w for w in tess_words
              if cell["x0"] <= (w[1] + w[2]) / 2 <= cell["x1"]
              and row["y0"] - 4 <= w[3] and w[3] <= row["y1"] + 4]
    return " ".join(w[0] for w in picked).strip()


def cells_in_bands(row, bands, tess_words=None):
    """Put each cell in the band its own middle falls in, and reconcile it.

    Two engines read every cell. Identical readings are confident; where one
    drops the spaces the other kept, the spaced reading wins, because an
    engine loses spaces and never invents them. Anything else is left flagged
    rather than picked between.
    """
    out = ["" for _ in bands]
    flags = [None for _ in bands]
    box = [None for _ in bands]
    for c in row["cells"]:
        mid = (c["x0"] + c["x1"]) // 2
        for i, (a, b) in enumerate(bands):
            if a <= mid < b:
                text, status = c["text"], "single"
                if tess_words is not None:
                    other = second_reading(row, c, tess_words)
                    if other:
                        from verify_names import reconcile
                        text, status = reconcile(c["text"], other)
                out[i] = (out[i] + " " + text).strip()
                if box[i] is None:
                    box[i] = [c["x0"], c["x1"]]
                else:
                    box[i][0] = min(box[i][0], c["x0"])
                    box[i][1] = max(box[i][1], c["x1"])
                if status not in ("confident", "reconciled", "single"):
                    flags[i] = status
                break
    return out, flags, box


def aligned(boxes, space_w):
    """Do these cells sit in a drawn column, or just happen to share a gap?

    A column is painted at a fixed x, so its cells agree on an edge: the left
    one normally, the right one where the values are numbers. Text that merely
    falls either side of an accidental gap -- a terminal beside a webcam
    inset, a paragraph's ragged edge -- agrees on neither, and without this
    test such a frame comes back as a confident two-column table of prose.
    """
    have = [b for b in boxes if b]
    if len(have) < 2:
        # one cell cannot disagree with itself; absence of evidence is not
        # evidence of misalignment, and rejecting here loses a real column
        # whose neighbours happen to be blank
        return True
    for side in (0, 1):
        vals = [b[side] for b in have]
        mid = statistics.median(vals)
        if statistics.median([abs(v - mid) for v in vals]) <= space_w * 1.5:
            return True
    return False


def belongs(row, bands, tess_words):
    """Is this row one of the table's, judged only by its columns?

    Every column filled but at most one, one cell to each, and no cell of the
    row left over. The last two matter as much as the first: without them the
    toolbar
    above the window "fits" because the cells falling outside the columns are
    quietly ignored, and the path bar along the bottom "fits" because its
    eight crumbs happen to land two to a column.
    """
    vals, _, _ = cells_in_bands(row, bands, tess_words)
    # ONE column may be empty. A value can be missing from a row that is
    # plainly the table's own -- in the Finder window the mouse pointer sits
    # over a file name and neither engine reads it -- and treating that as a
    # different table cost the whole thing its heading: the four-column table
    # fell to two rows, a three-column one formed under it out of the sixteen
    # files' dates and sizes, and the bigger one won with a date for a
    # heading. A missing value is a missing value. What is NOT relaxed is the
    # rest: one cell to a column and nothing left over, which is what keeps
    # the toolbar and the path bar out.
    if sum(1 for v in vals if not v.strip()) > 1:
        return False
    seen = [0] * len(bands)
    for c in row["cells"]:
        mid = (c["x0"] + c["x1"]) // 2
        for i, (a, b) in enumerate(bands):
            if a <= mid < b:
                seen[i] += 1
                break
        else:
            return False
    return all(n == 1 for n in seen)


def reach(found, rows, tess_words):
    """Give each table back the rows above and below that are still its own.

    The corridors are found from the rows that share them, and some of a
    table's rows do not: Finder left-aligns "Size" over sizes it
    right-aligns, so its heading crosses the very corridor its column stands
    on; the selected row is drawn white on a green fill, which changes what
    counts as blank across it; and one long file name runs within two spaces
    of the next column, closing the corridor for that row alone. Left there,
    a table names its columns after its first file and sheds its last rows
    into a second table of two columns that is really the same one.

    Nothing here loosens the corridor test, which is what keeps prose from
    reading as a table. The columns are already settled. This only asks of
    each neighbouring row whether it still fills them, one cell to a column,
    with nothing left over -- and stops at the first row that does not.

    Where two tables both want a row, the one with more columns takes it, the
    same order in which the tables were chosen. A table left with too few rows
    to be one is dropped.
    """
    order = sorted(range(len(found)), key=lambda i: -found[i]["columns"])
    owner = {}
    for i in order:
        for k in range(found[i]["first"], found[i]["last"] + 1):
            owner.setdefault(k, i)

    def free(k, i):
        held = owner.get(k)
        return held is None or found[held]["columns"] < found[i]["columns"]

    for i in order:
        b = found[i]
        for step in (-1, 1):
            k = (b["first"] if step < 0 else b["last"]) + step
            while 0 <= k < len(rows) and free(k, i) \
                    and belongs(rows[k], b["bands"], tess_words):
                owner[k] = i
                if step < 0:
                    b["first"] = k
                else:
                    b["last"] = k
                k += step

    kept = []
    for i, b in enumerate(found):
        mine = sorted(k for k, o in owner.items() if o == i)
        if len(mine) < MIN_ROWS:
            continue
        table, flags = [], []
        for k in mine:
            vals, fl, _ = cells_in_bands(rows[k], b["bands"], tess_words)
            table.append(vals)
            flags.append(fl)
        b["header"], b["rows"] = table[0], table[1:]
        b["headflags"], b["flags"] = flags[0], flags[1:]
        b["y0"], b["y1"] = rows[mine[0]]["y0"], rows[mine[-1]]["y1"]
        kept.append(b)
    kept.sort(key=lambda b: b["y0"])
    return kept


def read_list(png_path):
    """Read a column view back as a table, or say plainly that it is not one."""
    bgr = cv2.imread(png_path)
    if bgr is None:
        return {"is_list": False, "why": "could not read the image"}
    bgr = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3),
                     interpolation=cv2.INTER_LANCZOS4)
    big = png_path.replace(".png", "_3x.png")
    cv2.imwrite(big, bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = note_reader.ink_mask(gray)

    # the cell engine: one box per value, which is the shape a column view
    # actually has. The line engine merges a whole row of cells into one
    # string and the pairing is lost before it starts.
    from tree_reader import ocr_rows
    cells_in = [c for c in ocr_rows(big) if c["text"].strip()]
    if len(cells_in) < MIN_ROWS:
        return {"is_list": False, "why": "too little text to be a list"}
    rows = group_rows(cells_in)
    if len(rows) < MIN_ROWS:
        return {"is_list": False, "why": "too few rows to be a list"}

    # the second engine, read once over the pane, for reconciling each cell
    tess = note_reader.tess_rows(big, gray)
    tess_words = []
    for r in tess:
        for w in (r.get("words") or []):
            tess_words.append((w[0], w[1], w[2], r["y0"], r["y1"]))

    space_w = space_width(tess) or (statistics.median(
        [r["y1"] - r["y0"] for r in rows]) * 0.3)
    at = {id(r): i for i, r in enumerate(rows)}
    found = []
    for block_rows, corrs in blocks(mask, rows, space_w)[0]:
        bands = bands_from(corrs, mask.shape[1])
        table, flagged, boxes = [], [], []
        for r in block_rows:
            vals, flags, box = cells_in_bands(r, bands, tess_words)
            table.append(vals)
            flagged.append(flags)
            boxes.append(box)
        # A column view fills its columns on the rows it covers. A majority is
        # not enough: prose whose lines happen to stop short leaves a gap, and
        # text beyond it -- a webcam inset in the corner of a screen recording
        # -- fills the far band on half the rows, which was enough to return a
        # terminal as a confident two-column table.
        #
        # But ONE row may leave a column blank, for the same reason one row of
        # a table may be missing a value: in the Finder window the mouse
        # pointer sits over a file name and neither engine reads it. Demanding
        # every row cost the Name column, and with it the heading -- the four
        # cells of "Name / Date Modified / Size / Kind" no longer fitted the
        # three bands that were left, so the table named itself after its first
        # file: "Jun 12, 2026 at 11:03 AM / 1 KB / Markdo...text file". The
        # rule `belongs` already runs on -- a missing value is a missing value
        # -- read down a column instead of across a row.
        #
        # One blank of thirteen is 0.92; the webcam inset filled its band on
        # half the rows, and half is still refused.
        blanks = [sum(1 for row in table if not row[i].strip())
                  for i in range(len(bands))]
        keep = [i for i, n in enumerate(blanks) if n <= 1
                and aligned([row[i] for row in boxes], space_w)]
        if len(keep) < 2:
            continue
        bands = [bands[i] for i in keep]
        table = [[row[i] for i in keep] for row in table]
        flagged = [[row[i] for i in keep] for row in flagged]
        # The header is the first row that fills every column -- and there
        # must BE one. A set of columns nothing spans is not a table: it is
        # prose with a ragged edge, and text found on a webcam inset beside
        # it filling one band on half the rows is enough to fake the rest.
        header, body, hflags, headflags = None, table, flagged, None
        for i, row in enumerate(table):
            if all(c.strip() for c in row):
                header, body, hflags = row, table[i + 1:], flagged[i + 1:]
                headflags = flagged[i]
                break
        if header is None or not body:
            continue
        found.append({"columns": len(bands), "bands": bands,
                      "header": header, "rows": body, "flags": hflags,
                      "headflags": headflags,
                      "first": at[id(block_rows[0])],
                      "last": at[id(block_rows[-1])],
                      "y0": block_rows[0]["y0"], "y1": block_rows[-1]["y1"]})
    found = reach(found, rows, tess_words)
    if not found:
        return {"is_list": False,
                "why": "no run of rows shares a blank corridor between them"}
    return {"is_list": True, "blocks": found, "space_width": space_w,
            "columns": max(b["columns"] for b in found)}


def render(res):
    if not res.get("is_list"):
        return f"NOT A LIST VIEW - {res.get('why')}"
    out = []
    for bi, b in enumerate(res["blocks"]):
        head = b["header"] or [f"col {i+1}" for i in range(b["columns"])]
        widths = [max([len(head[i])] + [len(r[i]) for r in b["rows"]])
                  for i in range(len(head))]
        if len(res["blocks"]) > 1:
            out.append(f"[block {bi + 1}: {b['columns']} columns]")
        out.append("| " + " | ".join(h.ljust(w) for h, w in zip(head, widths)) + " |")
        out.append("|" + "|".join("-" * (w + 2) for w in widths) + "|")
        for r in b["rows"]:
            out.append("| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |")
        unsettled = [(r[i], f[i]) for r, f in zip(b["rows"], b.get("flags") or [])
                     for i in range(len(r)) if f[i]]
        for text, why in unsettled:
            out.append(f"    unsettled ({why}): {text!r}")
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    res = read_list(sys.argv[1])
    print(render(res))
