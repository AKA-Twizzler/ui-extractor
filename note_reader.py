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
import machine

INK_MARGIN = 26        # how far from local background a pixel counts as ink
GUTTER_SPAN = 2.4      # gutter searched, in multiples of the row's height
BOLD_RATIO = 1.18      # stroke this much above the body's is bold
LEVEL_GAP = 0.07       # height clusters closer than this are one size
# An ordered list draws its number, then a GAP, then the text. Without
# requiring that gap a version number at the start of a wrapped line
# ("2.1.176 is effectively...") reads as list item 2, and the line then
# refuses to rejoin the sentence it belongs to.
NUMBERED = re.compile(r"^\s*(\d+)\s*[.)]\s+")
# what a drawn bullet turns into when an engine reads it as a character
BULLET_CHARS = "\u00b7\u2022\u2219\u25aa\u25cf\u25e6\u00bb\u203a\u2023-"
# The lowercase letters that are drawn between the baseline and the x-height
# with nothing above or below: no ascender, no descender, no dot. A word made
# of these reports the size the line is SET in. A word of capitals, digits or
# punctuation is drawn to the cap height instead, which is around half again
# as tall, so it reports a size the line is not set in at all.
X_BAND = set("acemnorsuvwxz")


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


def row_x_height(mask, row):
    """The size THIS ROW is set in: what most of its words are set in.

    Measured across the whole row, an inline code span stretches the answer,
    because it is set in another face at another size and its ink lands
    outside the row's own band. A prose line carrying one such span then
    measures as tall as a small heading and is marked as one.

    A heading is uniformly larger -- every word of it. So the row's size is
    the median of its words' sizes, which one odd span cannot move.

    And only the words that can REPORT that size are asked. A digit and a
    capital are drawn to the cap height, half again as tall as the lowercase
    the line is set in, so a line dense in numbers measures as a line set
    larger -- and is then marked as a heading it never was. Measured on a
    daily note, against a body of 1.00:

        zero status data. OTT census: 6,285 active / 11,484 ...   1.18   1.05
        * CJ ads check (late session): Conf TRUE CPL $0.79 ...    1.09   1.00
        Thursday, June 11, 2026                                  1.59   1.57
        Index                                                    1.45   1.45
        Detail                                                   1.64   1.64
        The permission-classifier lesson (banked)                1.32   1.32

    The first two are sentences in the middle of a paragraph and came back as
    headings; the four below them are the note's real headings and do not
    move. A row with no such word left -- a title set as a bare date, an
    all-capital label -- has nothing to measure but its capitals, so it is
    measured as before rather than guessed at.
    """
    words = row.get("words") or []
    if len(words) < 2:
        return x_height(mask, row["y0"], row["y1"], row["x0"], row["x1"])
    speaking = [w for w in words if any(c in X_BAND for c in w[0])]
    sizes = [x_height(mask, row["y0"], row["y1"], w[1], w[2])
             for w in (speaking or words)]
    sizes = [s for s in sizes if s > 0]
    if not sizes:
        return x_height(mask, row["y0"], row["y1"], row["x0"], row["x1"])
    return float(statistics.median(sizes))


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

    A row is never thrown away for its first word alone. Where a mark in the
    gutter is read as a character -- a hanging bullet, an edge of the window
    chrome -- it joins the row and drags the row's left edge out of the
    column, and the whole sentence goes with it. Measured on a daily note:
    one stray 'N' at x=554 against a margin of 659 lost the line

        tv folder") flipped my late-night pessimism: LTV ~$250, so the old
        campaign's $28.57/trial

    from the middle of a paragraph, with nothing said. So the leading words
    outside the column are taken off and the row is judged by where its text
    really starts -- the same rule clip_to_column already applies at the other
    edge, and for the same reason: a row cannot be dropped whole without
    losing the real text.
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
    out = []
    for r in rows:
        if lo <= r["x0"] <= hi:
            out.append(r)
            continue
        if r["x0"] > hi:
            continue                    # chrome standing off to the right
        words = r.get("words") or []
        kept = [w for w in words if w[1] >= lo]
        if not kept or not (lo <= kept[0][1] <= hi):
            continue                    # nothing of this row is in the column
        r = dict(r)
        r["words"] = kept
        r["text"] = " ".join(w[0] for w in kept)
        r["x0"] = kept[0][1]
        out.append(r)
    return out


# The chat, console and note readers each enlarge the same pane the same way
# and hand the same pixels to tesseract -- three identical subprocess runs
# per pane, measured. Keyed on the exact pixels tesseract would be given, so
# a hit is identical by construction; a fresh copy goes back every time
# because callers mark up the rows.
_TESS_MEMO = {}
_TESS_HITS = 0


def tess_rows(png_path, gray):
    """Lines of the note, read with tesseract.

    Tesseract is the primary reader HERE and RapidOCR is the primary reader
    for file trees, because that is what each measured best at. On running
    prose RapidOCR drops the spaces — "Did themanual 2.1.178review byhand" —
    while tesseract returns the sentence with its spacing, punctuation and
    quotation marks intact. On a tree of short names the ranking reverses.
    Neither is better in general; each is used where it wins.
    """
    import copy
    import hashlib
    global _TESS_HITS
    ink = 255 - gray if float(np.median(gray)) < 128 else gray
    # its own name on purpose: `key` is rebound as a loop variable below,
    # and the store at the end must file under the pixels' fingerprint --
    # the suite caught exactly that
    memo_key = hashlib.md5(ink.tobytes()).hexdigest()
    if memo_key in _TESS_MEMO:
        _TESS_HITS += 1
        return copy.deepcopy(_TESS_MEMO[memo_key])
    work = png_path.replace(".png", "_tess.png")
    cv2.imwrite(work, ink)
    # encoding: tesseract writes UTF-8 whatever the machine's locale is, and
    # Windows decodes a pipe in cp1252 unless told, which turns one curly
    # quote into three wrong characters and loses the cell it stood in
    r = subprocess.run([machine.tesseract_or_refuse(), work, "stdout",
                        "-l", "eng", "--psm", "4", "tsv"],
                       capture_output=True, text=True, encoding="utf-8")
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
            "words": [(t, int(w["left"]), int(w["left"]) + int(w["width"]))
                      for w, t, _ in ws],
        })
    rows.sort(key=lambda r: (r["y0"], r["x0"]))
    if len(_TESS_MEMO) > 64:
        _TESS_MEMO.clear()
    _TESS_MEMO[memo_key] = copy.deepcopy(rows)
    return rows


def second_engine_rows(big_path):
    """The other engine's reading of the same pixels, as boxed lines."""
    try:
        from tree_reader import ocr_rows
        return ocr_rows(big_path)
    except Exception:
        return []


def text_at(second, row, pad):
    """What the other engine read across this row."""
    picked = [c for c in second
              if row["y0"] - pad <= (c["y0"] + c["y1"]) / 2 <= row["y1"] + pad
              and c["x1"] > row["x0"] - pad and c["x0"] < row["x1"] + pad]
    picked.sort(key=lambda c: c["x0"])
    text = " ".join(c["text"] for c in picked).strip()
    # the other engine sees the drawn bullet as well, and it has already been
    # taken off the primary reading; left on, the two never agree
    while text[:1] in BULLET_CHARS and len(text) > 2:
        text = text[1:].lstrip()
    return text


def reconcile_rows(rows, big_path, body_h):
    """Read every line twice and keep what the two engines agree on.

    One engine loses spaces inside a word; the other loses a glyph it cannot
    name, welding two version numbers together where a rendered arrow stood.
    Neither is trusted alone. Where the letters match, the fuller reading
    wins, because an engine drops what it cannot name and never invents it;
    where they do not, the line is left flagged rather than picked between.
    """
    second = second_engine_rows(big_path)
    if not second:
        return rows
    from verify_names import reconcile
    for r in rows:
        other = text_at(second, r, body_h * 0.4)
        if not other:
            r["read_status"] = "unverified"
            continue
        text, status = reconcile(r["text"], other)
        r["text_primary"] = r["text"]
        r["text"] = text
        r["read_status"] = status
        r["text_second"] = other
        if status == "cut":
            # both tails ride with the row: the head is the reading, the
            # tails are what each engine made of the pixels past the cut
            from verify_names import agreed_head
            _, tails = agreed_head(r["text_primary"], other)
            r["cut_tails"] = list(tails or ())
    # Each line's own verdict, measured in the characters it is worth, taken
    # HERE while the lines are still separate. A wrapped paragraph is joined
    # further down and the joined row can only carry one status -- the first
    # line's -- so a paragraph whose opening line the two engines differed on
    # counted as wholly unconfirmed though every line after it was confirmed.
    # Measured on a daily note: one 700-character paragraph, seven of its
    # eight lines backed, dragging the page from confirmed to refused.
    for r in rows:
        n = len(r.get("text") or "")
        r["all_chars"] = n
        r["backed_chars"] = n if r.get("read_status") in BACKED_STATUS else 0
    return rows


def read_note(png_path, engine=None):
    bgr = cv2.imread(png_path)
    # everything is measured on a 3x enlargement: strokes are two or three
    # pixels at native size and the measurement can only land on whole values
    bgr = machine.enlarge(bgr, 3)
    big_path = png_path.replace(".png", "_3x.png")
    cv2.imwrite(big_path, bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = ink_mask(gray)
    rows = tess_rows(big_path, gray)
    if not rows:
        return {"rows": [], "markdown": ""}
    rows.sort(key=lambda r: (r["y0"], r["x0"]))
    for r in rows:
        r["xh"] = row_x_height(mask, r)
    heights = [r["xh"] for r in rows if r["xh"] > 0]
    body = statistics.median(heights) if heights else 1.0
    rows = note_body(rows, body)
    heights = [r["xh"] for r in rows if r["xh"] > 0]
    body = statistics.median(heights) if heights else 1.0

    props, body_rows = properties_block(rows, body)
    # the sizes that define heading levels come from the note's own text. The
    # filename Obsidian prints above the note is the biggest text on screen,
    # and left in the reckoning it takes the top rank and pushes every real
    # heading down one.
    body_heights = [r["xh"] for r in body_rows if r["xh"] > 0]
    if body_heights:
        body = statistics.median(body_heights)
    rows = body_rows
    heights = body_heights or heights
    # Order matters here. The markers are found FIRST, because a row that
    # carries its own bullet begins a new line and must never be swallowed as
    # the wrapped tail of the line above it. Then the wraps are joined, once.
    # Only then are the sizes clustered into heading levels, because an
    # unjoined heading tail is measured as its own size, lands between two
    # real ranks and blurs them together — which costs a genuine smaller
    # heading its rank.
    for r in rows:
        r["marker"] = gutter_marker(mask, gray, r, body * 1.4)
        # the application draws the bullet as a glyph, and OCR often reads it
        # as a leading character rather than leaving it in the gutter
        lead = r["text"][:1]
        if lead and lead in BULLET_CHARS and len(r["text"]) > 2:
            r["marker"] = "bullet"
            r["text"] = r["text"][1:].strip()
        m = NUMBERED.match(r["text"])
        r["number"] = int(m.group(1)) if m else None
        # provisional, only to keep a heading from joining a body line
        r["heading"] = 1 if r["xh"] >= body * 1.10 else 0
    # only now is the text read a second time: reconciling first would replace
    # the line and take the drawn bullet off it, and the row would rejoin the
    # line above as if it had never started a new one
    rows = reconcile_rows(rows, big_path, body)

    # the column's right edge is where full lines end, taken as the busiest
    # right-hand position rather than the furthest, so one stray wide row
    # cannot push it out and stop every wrap from joining
    edges = sorted(r["x1"] for r in rows)
    right = edges[int(len(edges) * 0.75)] if edges else 0
    rows = clip_to_column(rows, right)
    rows = join_wraps(rows, right, body)

    heights = [r["xh"] for r in rows if r["xh"] > 0]
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
        # Nearest size wins. A one-sided cutoff needs a tolerance and drops
        # the row that sits just under it: two headings of the same rank
        # measure a pixel apart, and the shorter one loses its mark. Asking
        # which size this row is CLOSEST to -- the body's, or one of the
        # heading sizes -- needs no tolerance and cannot drop either.
        sizes = [1.0] + list(levels)
        nearest = min(range(len(sizes)), key=lambda i: abs(ratio - sizes[i]))
        level = nearest  # index 0 is the body itself
        r["height_ratio"] = round(ratio, 2)
        r["heading"] = level
        r["bold"] = bool(level == 0 and st >= body_stroke * BOLD_RATIO)
        r["stroke"] = round(st, 2)
        # indentation is counted in whole steps from the body's own margin,
        # and capped: a value sitting far right in a property panel is not
        # text indented eight levels deep
        r["indent"] = max(0, min(4, int(round((r["x0"] - left) / max(1.0, body * 1.6)))))
        # the ink's colour, where it is unmistakable -- see row_ink_color
        r["color"] = (row_ink_color(bgr, (r["x0"], r["y0"],
                                          r["x1"], r["y1"]))
                      if sum(ch.isalnum() for ch in r["text"]) >= 3
                      else None)
    body_rows = rows
    md = to_markdown(body_rows)
    if props:
        md = ("---\n" + "\n".join(f"{k}: {v}" for k, v in props)
              + "\n---\n" + md)
    return {"rows": rows, "properties": props, "body_rows": body_rows,
            "body_height": body, "levels": levels, "backed": backed_share(rows),
            "body_stroke": round(body_stroke, 2), "markdown": md}


# Colour is claimed only where it is unmistakable, and the bound is
# measured, not chosen. Across an ads manager, an Obsidian vault, a macOS
# desktop and a live chat: plain text reads saturation 0 to 25, coloured
# text 68 to 153 -- blue links, red and yellow chat handles, a cyan
# button -- and nothing measured between. The bound sits mid-gap at 45.
# Grey, white and black are the unmarked default, never a claim.
ROW_SAT = 45
_HUES = ((10, "red"), (22, "orange"), (33, "yellow"), (78, "green"),
         (100, "cyan"), (128, "blue"), (155, "purple"), (175, "pink"),
         (181, "red"))


def row_ink_color(bgr, box):
    """This row's ink colour by name, or None where it is plain.

    The dominant ink pixel's hue, asked only where there is enough ink to
    measure -- thirty pixels -- and the saturation clears the measured
    gap. The caller decides whether the row's text is worth asking about;
    this answers only what colour the ink is.
    """
    x0, y0, x1, y1 = box
    crop = bgr[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return None
    bg = np.median(crop.reshape(-1, 3), axis=0)
    ink = np.abs(crop.astype(np.int16) - bg).max(axis=2) > 60
    if int(ink.sum()) < 30:
        return None
    dom = np.median(crop[ink].reshape(-1, 3), axis=0) \
        .astype(np.uint8).reshape(1, 1, 3)
    h, s, _v = cv2.cvtColor(dom, cv2.COLOR_BGR2HSV)[0, 0]
    if int(s) < ROW_SAT:
        return None
    for top, name in _HUES:
        if int(h) <= top:
            return name
    return "red"


def first_word_width(row):
    """How wide this row's first word was drawn, from the row's own box.

    The row's box and its character count give the mean width of a character
    at whatever size this row is set in, so the first word's width follows
    without knowing the font, the zoom or the theme.
    """
    text = row["text"].strip()
    if not text:
        return 0.0
    per_char = (row["x1"] - row["x0"]) / max(1, len(text))
    return per_char * (len(text.split()[0]) + 1)


def clip_to_column(rows, right_edge):
    """Drop words drawn outside the note's text column.

    The application paints its own text beside the note — a status bar at the
    far right, a backlink count — and a word there sits on the same scan line
    as the note's last row, so OCR returns them as ONE row and the chrome ends
    up inside the sentence. A row cannot be dropped whole without losing the
    real text, so the chrome is removed word by word: a word that BEGINS past
    the margin where the note's lines end was never in the column.
    """
    out = []
    for r in rows:
        words = r.get("words") or []
        if not words:
            out.append(r)
            continue
        kept = [w for w in words if w[1] <= right_edge]
        if not kept:
            continue
        if len(kept) != len(words):
            r = dict(r)
            r["words"] = kept
            r["text"] = " ".join(w[0] for w in kept)
            r["x1"] = max(w[2] for w in kept)
        out.append(r)
    return out


def join_wraps(rows, right_edge, body_h):
    """Put a wrapped line back onto the line it came from.

    A paragraph that runs past the width of the pane is drawn as several rows,
    and each is a separate result from OCR. Without this a paragraph comes
    back as a stack of fragments, which is not what the screen shows.

    The test is not "did this row end near the margin", because that needs a
    tolerance and gets it wrong: a heading is set in bigger type, so its words
    are wider and it wraps a long way short of where prose wraps. The question
    that needs no tolerance is whether the NEXT row's first word would have
    fitted in the space left on this one. If it would have, the line ended
    because the writer ended it; if it would not have, the application moved
    it down and the two rows are one line.
    """
    out = []
    for r in rows:
        close = (out
                 and (right_edge - out[-1]["x1"]) < first_word_width(r)
                 and abs(r["y0"] - out[-1]["y1"]) < body_h * 3.0)
        # a heading wraps too, and its second line must rejoin the first.
        # Left apart, the wrapped half is measured as its own size and lands
        # between two real heading ranks, blurring the clusters so a genuine
        # smaller heading below it stops being recognised as a heading at all.
        same_size = (out and abs(r["xh"] - out[-1]["xh"]) <= max(1.0, body_h * 0.12))
        joinable = (close and not r["marker"] and not r["number"]
                    and ((not r["heading"] and not out[-1]["heading"])
                         or (out[-1]["heading"] and same_size)))
        if joinable:
            # the joined line is worth what its parts were worth -- see
            # reconcile_rows, which set these while the parts were separate
            out[-1]["all_chars"] = (out[-1].get("all_chars", 0)
                                    + r.get("all_chars", 0))
            out[-1]["backed_chars"] = (out[-1].get("backed_chars", 0)
                                       + r.get("backed_chars", 0))
            out[-1]["text"] = out[-1]["text"].rstrip() + " " + r["text"].lstrip()
            out[-1]["xh"] = max(out[-1]["xh"], r["xh"])
            out[-1]["x1"] = r["x1"]
            out[-1]["y1"] = r["y1"]
        else:
            out.append(dict(r))
    return out


def split_key_value(row, body_h, min_gap=3.0):
    """Split a field row into its label and its value.

    A properties panel draws the label on the left and the value away to the
    right, and OCR returns the whole line as one string — "status active" —
    which reads as a sentence and is not one. The gap between them is far
    wider than the space between words, so that is where it splits.
    """
    words = row.get("words") or []
    if len(words) < 2:
        return None
    gaps = [(words[i + 1][1] - words[i][2], i) for i in range(len(words) - 1)]
    widest, at = max(gaps)
    if widest < body_h * min_gap:
        return None
    key_words = [t for t, _, _ in words[:at + 1]]
    # the field's little icon comes back as a stray one-character token; a real
    # field name never starts with one
    while len(key_words) > 1 and len(key_words[0].strip(" :=+©@")) <= 1:
        key_words.pop(0)
    key = " ".join(key_words).strip(" :=+©@\u2261\u4e09")
    val = " ".join(t for t, _, _ in words[at + 1:]).strip(" :=+©@")
    if not key or not val:
        return None
    return key, val, row["x0"], words[at + 1][1]


def is_button(text):
    """The "add a property" button, however the engine drew its plus sign.

    It sits inside the properties panel and is not a property. The plus is a
    drawn glyph, so one engine reads it as "+", another as "++", and a third
    loses it -- the test is the words, not the sign.
    """
    t = text.lstrip("+ \t").lstrip()
    return t.lower().startswith("add property") or t.lower().startswith("add a property")


def properties_block(rows, body_h):
    """The panel of key/value fields above a note's body, if there is one.

    It is not part of the prose and must not be read as one: its little field
    icons look exactly like checkboxes, and its right-hand values sit far from
    the body margin so they read as deep indentation. It is everything before
    the first heading that pairs a label on the left with a value to its right.

    A wide gap alone does not make a field, and taking it for one costs more
    than a wrong fence: everything above the last field is dropped as the
    note's header, so a card whose last line happens to split loses its whole
    body. A letterspaced label -- "TYPING IT YOURSELF" -- splits at a gap
    wider than three body heights, and so does a line of prose with a drawn
    bullet in front of it.

    What a real panel has and neither of those has is a COLUMN. Its labels all
    start at one x and its values all start at another:

      status   active        key x0 1098   value x0 1426
      project  personal          "  1098       "    1427
      type     log               "  1098       "    1427
      created  06/16/2026        "  1097       "    1426

    against a card that read as one, where the values began at 786 and 1830.
    So the columns must hold to within a character of the text's own width,
    which the rows themselves supply -- no fixed number.
    """
    fields, last = [], -1
    for i, r in enumerate(rows[:12]):
        kv = split_key_value(r, body_h)
        # A field's LABEL is a word. A row of window furniture -- the menu
        # bar's icons across the top of a wider crop -- splits at a wide gap
        # like a field does and arrives here as ".: he . C8 @we eo @ #.",
        # which is not a field name and must not become frontmatter.
        if kv and any(ch.isalpha() for ch in kv[0]) and not is_button(kv[0]):
            fields.append((i, kv, r))
            last = i
    if len(fields) < 2:
        return [], rows
    char = statistics.median(
        [(r["x1"] - r["x0"]) / max(1, len(r["text"])) for _, _, r in fields])
    for col in (2, 3):                       # where the keys start, then the values
        edges = [kv[col] for _, kv, _ in fields]
        if max(edges) - min(edges) > char:
            return [], rows
    # everything up to the last field row is the note's header: the filename
    # Obsidian shows above the note, and the properties panel itself. None of
    # it is prose, and counting the filename as a heading pushes every real
    # heading down a rank.
    body = [r for r in rows[last + 1:] if not is_button(r["text"])]
    return [(kv[0], kv[1]) for _, kv, _ in fields], body


# A document's lines are read twice, and this is the share of them the second
# engine backed. Measured: a real Obsidian note 1.00 and 0.89; the July 6
# stream's leaderboard 0.12; a frame of that stream's own overlay 0.00; a
# column of chat bubbles on a slide 0.50; the claude.ai sidebar, where every
# label carries a drawn icon, 0.33. Under this, what came back was not a
# document but the recogniser's best effort at a picture -- "## +M O L 8 | 0",
# "F Fi X | GC)" -- and it used to be printed as prose with nothing said.
BACKED = 2 / 3


# "cut" is a line both engines read alike up to an edge and as junk past it
# -- see verify_names.agreed_head; the head is a backed reading
BACKED_STATUS = ("confident", "reconciled", "ambiguous-symbol",
                 "ambiguous-glyph", "cut")


def backed_share(rows):
    """How much of this reading the second engine read too, by TEXT not by row.

    Counted by row, a two-character scrap of window chrome weighs as much as a
    full paragraph, and a page can fail on the scraps around it while every
    sentence on it is confirmed. Measured on a Facebook post inside an
    Obsidian-free frame: fourteen rows, nine of them backed, 0.64 against a
    gate of 0.67 -- so a page whose every paragraph was confirmed twice fell
    out of the document reader by three hundredths and came back as loose
    run-together text instead. The rows that outvoted it were

        4 :                 d5 560 ()1 31            Carson James (c)

    none of which is evidence about anything. By characters the same page is
    0.76, and the reading it was built to refuse -- a live stream's
    leaderboard, one line in eight -- stays where it was, because there the
    unbacked lines are the long ones.

    So the question is not "how many rows were confirmed" but "how much of
    what this says was confirmed", which is what the gate always meant.
    """
    if not rows:
        return 0.0
    # each line's own verdict, in the characters it was worth, summed through
    # the wrap join -- a joined paragraph carries what its parts carried
    total = sum(r.get("all_chars", len(r.get("text") or "")) for r in rows)
    if not total:
        return 0.0
    good = sum(r.get("backed_chars",
                     len(r.get("text") or "")
                     if r.get("read_status") in BACKED_STATUS else 0)
               for r in rows)
    return good / total


def to_markdown(rows):
    out = []
    for r in rows:
        text = r["text"]
        if r.get("read_status") in ("uncertain", "unverified"):
            other = r.get("text_second")
            text += ("   <- only one engine read this" if not other
                     else f"   <- the other engine read {other!r}")
        elif r.get("read_status") == "cut":
            tails = r.get("cut_tails") or []
            rest = " / ".join(repr(t) for t in tails if t)
            text += ("   <- the line runs on past the edge; past it the "
                     f"engines read {rest}" if rest else
                     "   <- the line runs on past the edge")
        pad = "  " * max(0, min(4, r["indent"]))
        if r["heading"]:
            line = f"{pad}{'#' * min(6, r['heading'])} {text}"
        elif r["marker"] == "checkbox":
            line = f"{pad}- [ ] {text}"
        elif r["marker"] == "checkbox-checked":
            line = f"{pad}- [x] {text}"
        elif r["marker"] == "bullet":
            line = f"{pad}- {text}"
        elif r["number"]:
            line = f"{pad}{text}"
        elif r["bold"]:
            line = f"{pad}**{text}**"
        else:
            line = f"{pad}{text}"
        # after the shape marks, so the suffix never lands inside them --
        # and behind the arrow, which every word-tracking reader skips
        if r.get("color"):
            line += f"   <- drawn in {r['color']}"
        out.append(line)
    return "\n".join(out)


def body_lines(markdown):
    """How many lines of a read note are actually text.

    The `---` fences of a properties block are structure the reader emits, not
    something it read, so counting them as lines lets two words become a
    document. On a stylised heads-up display the recogniser returned "we Me
    Bs: VE Ze Ss" and "ub: LN CONNECTED", the reader wrapped them in fences,
    and four lines came back where two garbled ones had been read.
    """
    return sum(1 for line in markdown.splitlines()
               if line.strip() and line.strip() != "---")


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
