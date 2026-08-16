#!/usr/bin/env python3
"""Read an open note back as markdown: the words AND the shape.

Reading the words is not enough. A note is headings, bold, bullets, numbers,
checkboxes and indentation, and none of that survives as characters on screen
— the application RENDERS it. There is no "#" to find and no "- [ ]" to find.
A heading is simply bigger text, a bullet is a drawn dot, a checkbox is a drawn
box. So every one of them is measured from pixels:

  heading      the row's X-HEIGHT against the body's, clustered — the distinct
               sizes above the body ARE the heading levels, in order. Not the
               height of the OCR box, which grows and shrinks with whatever
               letters happen to be on the line: a row with a "g" in it
               measures taller than the same size without one.
  bold         stroke thickness, as the mean width of an unbroken run of ink
               along the row. Measured on a 3x enlargement, because at native
               size a stroke is two or three pixels and the number can only
               land on whole values, which is not enough to separate bold from
               body at all.
  bullet       a small solid blob in the gutter, about as wide as it is tall
  checkbox     a box in the gutter: hollow means unticked, filled means ticked
  number       the application draws "1." as text, so OCR reads it directly
  indent       where the row's text starts, against the leftmost body row

Nothing here is a judgment and nothing is a fixed threshold in disguise: the
body's size and stroke are measured from this note, so a different theme, zoom
or font changes the numbers without changing the answer.
"""
import re
import statistics
import sys

import csv
import io
import os
import subprocess

import cv2
import numpy as np

INK_MARGIN = 26        # how far from local background a pixel counts as ink
GUTTER_SPAN = 2.4      # gutter searched, in multiples of the row's height
BOLD_RATIO = 1.18      # stroke this much above the body's is bold
LEVEL_GAP = 0.07       # height clusters closer than this are one size
NUMBERED = re.compile(r"^\s*(\d+)\s*[.)]\s*")
# what a drawn bullet turns into when an engine reads it as a character
BULLET_CHARS = "\u00b7\u2022\u2219\u25aa\u25cf\u25e6\u00bb\u203a\u2023-"


def ink_mask(gray):
    """Ink, whichever way the theme contrasts."""
    k = np.ones((25, 25), np.uint8)
    bg = cv2.medianBlur(gray, 21)
    lighter = cv2.subtract(gray, bg)
    darker = cv2.subtract(bg, gray)
    return cv2.max(lighter, darker) > INK_MARGIN


def stroke_width(mask):
    """Mean width of an unbroken horizontal run of ink.

    Mean, not median: a median over two- and three-pixel runs can only return
    2 or 3, which cannot separate bold from body. The mean moves continuously.
    """
    runs = []
    for row in mask:
        n = 0
        for v in row:
            if v:
                n += 1
            elif n:
                runs.append(n)
                n = 0
        if n:
            runs.append(n)
    runs = [r for r in runs if r <= 60]
    return float(np.mean(runs)) if runs else 0.0


def x_height(mask, y0, y1, x0, x1):
    """The height of the band where most of the row's ink sits.

    This is the letter size itself, independent of which letters are on the
    line. Ascenders and descenders are the thin tails of the profile; the
    body of the text is the fat middle, and that is what is measured.
    """
    cell = mask[max(0, y0):y1, max(0, x0):x1]
    if cell.size == 0:
        return 0.0
    profile = cell.sum(axis=1).astype(np.float32)
    if profile.max() <= 0:
        return 0.0
    return float((profile >= profile.max() * 0.5).sum())


def gutter_marker(mask, gray, row, body_h):
    """What is drawn to the left of this row's text, if anything."""
    y0, y1 = max(0, row["y0"] - 2), min(mask.shape[0], row["y1"] + 2)
    span = int(body_h * GUTTER_SPAN)
    x1 = max(0, row["x0"] - 2)
    x0 = max(0, x1 - span)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    cell = mask[y0:y1, x0:x1]
    if cell.sum() < 4:
        return None
    ys, xs = np.where(cell)
    w = xs.max() - xs.min() + 1
    h = ys.max() - ys.min() + 1
    if w > body_h * 1.6 or h > body_h * 1.6:
        return None                      # too big to be a marker
    fill = cell[ys.min():ys.max() + 1, xs.min():xs.max() + 1].mean()
    squareness = min(w, h) / max(1, max(w, h))
    if squareness < 0.55:
        return None
    if fill >= 0.72:
        return "bullet" if w <= body_h * 0.55 else "checkbox-checked"
    if fill <= 0.55 and w >= body_h * 0.5:
        return "checkbox"
    return "bullet" if w <= body_h * 0.55 else None


def levels_from(heights, body):
    """Turn the distinct sizes above the body into heading levels, largest first."""
    big = sorted({round(h / body, 2) for h in heights if h / body >= 1.10},
                 reverse=True)
    groups = []
    for r in big:
        if groups and abs(groups[-1][-1] - r) <= LEVEL_GAP:
            groups[-1].append(r)
        else:
            groups.append([r])
    return [statistics.mean(g) for g in groups]


def note_body(rows, body_h):
    """Drop the window chrome around the note: the tab strip and breadcrumb.

    The note's own lines occupy one column. Chrome does not: the breadcrumb
    sits far to the right of it and the menu bar far to the left. Anchoring on
    the COMMONEST left edge is wrong, because that is the body prose, which is
    indented further right than the headings — anchor there and every heading
    above the first paragraph is thrown away with the chrome.

    So the column is found first, then its leftmost edge, and everything
    inside that column is kept.
    """
    if not rows:
        return rows
    from collections import Counter
    bin_size = max(1.0, body_h)
    common = Counter(int(r["x0"] / bin_size) for r in rows).most_common(1)[0][0]
    near = [r["x0"] for r in rows if abs(int(r["x0"] / bin_size) - common) <= 3]
    if not near:
        return rows
    margin = min(near)
    lo, hi = margin - body_h * 1.5, margin + body_h * 8
    return [r for r in rows if lo <= r["x0"] <= hi]


def tess_rows(png_path, gray):
    """Lines of the note, read with tesseract.

    Tesseract is the primary reader HERE and RapidOCR is the primary reader
    for file trees, because that is what each measured best at. On running
    prose RapidOCR drops the spaces — "Did themanual 2.1.178review byhand" —
    while tesseract returns the sentence with its spacing, punctuation and
    quotation marks intact. On a tree of short names the ranking reverses.
    Neither is better in general; each is used where it wins.
    """
    work = png_path.replace(".png", "_tess.png")
    cv2.imwrite(work, 255 - gray if float(np.median(gray)) < 128 else gray)
    r = subprocess.run(["tesseract", work, "stdout", "-l", "eng",
                        "--psm", "4", "tsv"], capture_output=True, text=True)
    # QUOTE_NONE matters: note text contains quotation marks, and the default
    # parser treats them as field quoting, which swallows the row structure
    # and leaks raw table rows into the output as if they were prose
    reader = csv.reader(io.StringIO(r.stdout), delimiter="\t",
                        quoting=csv.QUOTE_NONE)
    header = next(reader, None)
    words = [dict(zip(header, row)) for row in reader
             if header and len(row) == len(header)]
    lines = {}
    for w in words:
        text = (w.get("text") or "").strip()
        if not text:
            continue
        try:
            conf = float(w["conf"])
        except (KeyError, ValueError):
            continue
        if conf < 0:
            continue
        key = (w["block_num"], w["par_num"], w["line_num"])
        lines.setdefault(key, []).append((w, text, conf))
    rows = []
    for key, ws in lines.items():
        text = " ".join(t for _, t, _ in ws)
        if len(text.strip()) < 2:
            continue
        rows.append({
            "text": text.strip(),
            "score": float(np.mean([c for _, _, c in ws])) / 100.0,
            "x0": min(int(w["left"]) for w, _, _ in ws),
            "x1": max(int(w["left"]) + int(w["width"]) for w, _, _ in ws),
            "y0": min(int(w["top"]) for w, _, _ in ws),
            "y1": max(int(w["top"]) + int(w["height"]) for w, _, _ in ws),
        })
    rows.sort(key=lambda r: (r["y0"], r["x0"]))
    return rows


def read_note(png_path, engine=None):
    bgr = cv2.imread(png_path)
    # everything is measured on a 3x enlargement: strokes are two or three
    # pixels at native size and the measurement can only land on whole values
    bgr = cv2.resize(bgr, (bgr.shape[1] * 3, bgr.shape[0] * 3),
                     interpolation=cv2.INTER_LANCZOS4)
    big_path = png_path.replace(".png", "_3x.png")
    cv2.imwrite(big_path, bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = ink_mask(gray)
    rows = tess_rows(big_path, gray)
    if not rows:
        return {"rows": [], "markdown": ""}
    rows.sort(key=lambda r: (r["y0"], r["x0"]))
    for r in rows:
        r["xh"] = x_height(mask, r["y0"], r["y1"], r["x0"], r["x1"])
    heights = [r["xh"] for r in rows if r["xh"] > 0]
    body = statistics.median(heights) if heights else 1.0
    rows = note_body(rows, body)
    heights = [r["xh"] for r in rows if r["xh"] > 0]
    body = statistics.median(heights) if heights else 1.0

    levels = levels_from(heights, body)
    strokes = []
    for r in rows:
        cell = mask[r["y0"]:r["y1"], r["x0"]:r["x1"]]
        # scaled by this row's own size, so a big heading is not "bold"
        strokes.append(stroke_width(cell) / max(0.4, r["xh"] / body))
    body_stroke = statistics.median([s for s in strokes if s > 0] or [1.0])

    left = min((r["x0"] for r in rows), default=0)
    for r, st in zip(rows, strokes):
        ratio = (r["xh"] / body) if body else 1.0
        level = 0
        for i, lv in enumerate(levels):
            if ratio >= lv - LEVEL_GAP / 2:
                level = i + 1
                break
        r["height_ratio"] = round(ratio, 2)
        r["heading"] = level
        r["bold"] = bool(level == 0 and st >= body_stroke * BOLD_RATIO)
        r["stroke"] = round(st, 2)
        r["marker"] = gutter_marker(mask, gray, r, body * 1.4)
        # the application draws the bullet as a glyph, and OCR often reads it
        # as a leading character rather than leaving it in the gutter
        lead = r["text"][:1]
        if lead and lead in BULLET_CHARS and len(r["text"]) > 2:
            r["marker"] = "bullet"
            r["text"] = r["text"][1:].strip()
        m = NUMBERED.match(r["text"])
        r["number"] = int(m.group(1)) if m else None
        # indentation is counted in whole steps from the body's own margin,
        # and capped: a value sitting far right in a property panel is not
        # text indented eight levels deep
        r["indent"] = max(0, min(4, int(round((r["x0"] - left) / max(1.0, body * 1.6)))))
    props, body_rows = properties_block(rows, body)
    right = max((r["x1"] for r in body_rows), default=0)
    body_rows = join_wraps(body_rows, right, body)
    md = to_markdown(body_rows)
    if props:
        pairs = []
        for r in props:
            pairs.append(r["text"])
        md = "---\n" + "\n".join(pairs) + "\n---\n" + md
    return {"rows": rows, "properties": props, "body_rows": body_rows,
            "body_height": body, "levels": levels,
            "body_stroke": round(body_stroke, 2), "markdown": md}


def join_wraps(rows, right_edge, body_h):
    """Put a wrapped line back onto the line it came from.

    A paragraph that runs past the width of the pane is drawn as several rows,
    and each is a separate result from OCR. A row that ends near the right
    edge of the text column did not finish — the next row is the rest of the
    same sentence, not a new one. Without this a paragraph comes back as a
    stack of fragments, which is not what the screen shows.
    """
    out = []
    for r in rows:
        joinable = (out and not r["heading"] and not r["marker"]
                    and not r["number"] and not out[-1]["heading"]
                    and out[-1]["x1"] >= right_edge - body_h * 2
                    and abs(r["y0"] - out[-1]["y1"]) < body_h * 2.5)
        if joinable:
            out[-1]["text"] = out[-1]["text"].rstrip() + " " + r["text"].lstrip()
            out[-1]["x1"] = r["x1"]
            out[-1]["y1"] = r["y1"]
        else:
            out.append(dict(r))
    return out


def properties_block(rows, body_h):
    """The panel of key/value fields above a note's body, if there is one.

    It is not part of the prose and must not be read as one: its little field
    icons look exactly like checkboxes, and its right-hand values sit far from
    the body margin so they read as deep indentation. It is everything before
    the first heading that pairs a label on the left with a value to its right.
    """
    first_heading = next((i for i, r in enumerate(rows) if r["heading"]), None)
    if first_heading is None or first_heading == 0:
        return [], rows
    head = rows[:first_heading]
    lefts = sorted(r["x0"] for r in head)
    if len(lefts) < 4:
        return [], rows
    spread = lefts[-1] - lefts[0]
    if spread < body_h * 4:
        return [], rows
    return head, rows[first_heading:]


def to_markdown(rows):
    out = []
    for r in rows:
        text = r["text"]
        pad = "  " * max(0, min(4, r["indent"]))
        if r["heading"]:
            out.append(f"{pad}{'#' * min(6, r['heading'])} {text}")
        elif r["marker"] == "checkbox":
            out.append(f"{pad}- [ ] {text}")
        elif r["marker"] == "checkbox-checked":
            out.append(f"{pad}- [x] {text}")
        elif r["marker"] == "bullet":
            out.append(f"{pad}- {text}")
        elif r["number"]:
            out.append(f"{pad}{text}")
        elif r["bold"]:
            out.append(f"{pad}**{text}**")
        else:
            out.append(f"{pad}{text}")
    return "\n".join(out)


if __name__ == "__main__":
    note = read_note(sys.argv[1])
    print(f"body height {note['body_height']:.0f}px, heading sizes "
          f"{[round(l,2) for l in note['levels']]}, body stroke "
          f"{note['body_stroke']}\n")
    if "--detail" in sys.argv:
        print(f"{'h/body':>6} {'stroke':>6} {'lvl':>3} {'bold':>5} {'marker':>17}  text")
        for r in note["rows"]:
            print(f"{r['height_ratio']:>6.2f} {r['stroke']:>6.2f} {r['heading']:>3} "
                  f"{str(r['bold']):>5} {str(r['marker']):>17}  {r['text'][:46]}")
    else:
        print(note["markdown"])
