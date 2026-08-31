#!/usr/bin/env python3
"""Read a live stream's chat log: who said it, and what they said.

    python3 chat_reader.py <frame.png>

A chat log is not prose and not a table. It is a stack of ENTRIES, and every
entry is the same three things: a small avatar in the gutter, a name, and a
message that may wrap onto further lines. Read as prose it comes back as
"Webby followed the LIVE creator SZ Trades joined", which is two people, two
events and no way to tell which words belong to whom.

Three measurements do the whole job, and each is a fact about the pixels:

    an entry begins   where an avatar sits in the gutter -- the same test
                      that finds a bullet in a note
    the name ends     where the COLOUR changes. A chat draws the name in one
                      colour and the message in another, so the name is the
                      leading run of words whose ink differs from the colour
                      most of the line is drawn in
    a line is text    when its spaces are about as wide as its characters.
                      This matters because the chat is drawn OVER video, and
                      the animation behind it puts loose glyphs on the same
                      scan lines; those "lines" have gaps of hundreds of
                      pixels between marks, where real text has fifteen

Stroke width was tried for the name and does not work: measured across four
entries the name scored 1.04, 0.86, 1.29 and 1.00 against the line's own
median, which is no separation at all. The wider gap after a name works in
three cases of four. Colour works in all four, so colour is what is used.
"""
import re
import statistics
import sys

import cv2
import numpy as np

import note_reader
import machine

GAP_TO_CHAR = 4.0      # a space wider than this many characters is not a space
MIN_ENTRIES = 2        # one entry is not a log
CONFIRMED = 0.34       # a third of a log's words are words the other engine
                       # read too: measured, one real log gives 0.79 and 0.50
                       # across two captures, and a heads-up display 0.00


def ink_colour(bgr, mask, y0, y1, x0, x1):
    """The mean colour of the ink in this box, or None if there is none."""
    cell = bgr[max(0, y0):y1, max(0, x0):x1]
    m = mask[max(0, y0):y1, max(0, x0):x1]
    if cell.size == 0 or not m.any():
        return None
    return cell[m].mean(axis=0)


def is_text_line(row):
    """Does this line's spacing look like writing, or like scattered marks?

    The chat is drawn over video, and whatever is animating behind it leaves
    glyphs on the same scan lines. Those come back as rows too. A real line of
    text sets its spaces at about the width of its characters; a scattered
    line has gaps of hundreds of pixels between marks.
    """
    words = row.get("words") or []
    if len(words) < 2:
        return False
    chars = sum(len(w[0]) for w in words)
    if chars < 4:
        return False
    char_w = sum(w[2] - w[1] for w in words) / chars
    gaps = [b[1] - a[2] for a, b in zip(words, words[1:])]
    return statistics.median(gaps) <= char_w * GAP_TO_CHAR


def split_wide_gaps(rows):
    """Cut a row wherever the gap is too wide to be a space.

    The recogniser returns a scan line, not a column, so a slide on the left
    of the frame and a chat log on the right come back as ONE row with a
    quarter of the picture between them. Left whole, the row begins at the
    slide's margin, the log's margin is never found, and three bullet points
    and their captions are reported as things people said.

    The width that is no longer a space is the one already measured for
    telling writing from scattered marks; a row is cut there instead of being
    thrown away, so the chat keeps its own half.
    """
    out = []
    for r in rows:
        words = r.get("words") or []
        if len(words) < 2:
            out.append(r)
            continue
        chars = sum(len(w[0]) for w in words)
        if chars < 4:
            out.append(r)
            continue
        char_w = sum(w[2] - w[1] for w in words) / chars
        piece = [words[0]]
        for a, b in zip(words, words[1:]):
            if b[1] - a[2] > char_w * GAP_TO_CHAR:
                out.append(dict(r, words=piece, x0=piece[0][1], x1=piece[-1][2],
                                text=" ".join(w[0] for w in piece)))
                piece = []
            piece.append(b)
        if piece:
            out.append(dict(r, words=piece, x0=piece[0][1], x1=piece[-1][2],
                            text=" ".join(w[0] for w in piece)))
    return out


def text_margin(rows, tol):
    """Where the chat's writing begins, leaving the avatars to its left.

    Every line of a chat -- an entry's first line and every line its message
    wraps onto -- begins at one x. The avatars stand in a second column to
    the left of it, and only entries have one. So the margin is the LEFTMOST
    column that the most lines share, and a mark further left than that is an
    avatar rather than a word.

    Measured on one frame: the avatars sit at 288, 296, 312 and 312, and the
    writing at 584, 587, 588, 592, 630 -- two columns, not a spread.
    """
    starts = []
    for r in rows:
        for w in (r.get("words") or []):
            starts.append((w[1], id(r)))
    if not starts:
        return 0
    starts.sort()
    clusters = []
    for x, rid in starts:
        if clusters and x - clusters[-1][0] <= tol:
            clusters[-1][1].add(rid)
        else:
            clusters.append((x, {rid}))
    if not clusters:
        return 0
    most = max(len(c[1]) for c in clusters)
    for x, rids in clusters:
        if len(rids) == most:
            return x
    return clusters[0][0]


def strip_avatar(row, margin):
    """Drop the marks standing left of the writing, and say if there were any.

    The engine reads the little picture as a character or two -- "&", "W",
    "I>." -- so it cannot be told from a word by its text. It can be told by
    where it stands.
    """
    words = row.get("words") or []
    kept = [w for w in words if w[1] >= margin]
    return kept, len(kept) != len(words)


def split_name(gray, mask, row, words, scale=1):
    """Split an entry into the name and the message, at the change in colour.

    A chat draws the name in one colour and the message in another, so the
    line's brightness STEPS UP or DOWN once, where the name ends. The split is
    the place that step is largest.

    A step alone is not enough, because every line varies a little. So the
    step has to stand clear of that variation: it counts only when it is
    several times the spread of the message's own words. Measured on four
    entries, a real name gives a step of 16 to 22 grey levels against a
    message spread of 2 to 3; a wrapped line with no name in it gives 6
    against the same spread, and is correctly left alone.

    Distance from the line's median colour was tried first and does not
    separate them: names scored 12 to 20 and message words 0 to 15.
    """
    if len(words) < 2:
        return None, " ".join(w[0] for w in words)
    # Colour is read from the ORIGINAL pixels, not the enlargement the text
    # was recognised on. Enlarging invents values between the real ones, and
    # measured on the enlargement the message's own words vary by 7 grey
    # levels instead of 2 -- enough to swallow the step at the name and split
    # "Hoosier3D followed" as a name. On the real pixels the same four entries
    # separate cleanly: names at 119-125, messages at 133-145.
    bright = []
    for w in words:
        y0, y1 = row["y0"] // scale, row["y1"] // scale
        x0, x1 = w[1] // scale, w[2] // scale
        cell = gray[y0:y1, x0:x1]
        m = mask[y0:y1, x0:x1]
        bright.append(float(cell[m].mean()) if m.any() else None)
    pairs = [(w, b) for w, b in zip(words, bright) if b is not None]
    if len(pairs) < 2:
        return None, " ".join(w[0] for w in words)
    vals = [b for _, b in pairs]
    best_k, best_gain = None, 0.0
    for k in range(1, len(vals)):
        gain = abs(statistics.mean(vals[k:]) - statistics.mean(vals[:k]))
        if gain > best_gain:
            best_k, best_gain = k, gain
    if best_k is None:
        return None, " ".join(w[0] for w, _ in pairs)
    tail = vals[best_k:]
    spread = statistics.pstdev(tail) if len(tail) > 1 else 0.0
    if best_gain < max(6.0, spread * 3):
        return None, " ".join(w[0] for w, _ in pairs)
    name = " ".join(w[0] for w, _ in pairs[:best_k])
    rest = " ".join(w[0] for w, _ in pairs[best_k:])
    return name, rest


def _words(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3]


def confirmed_elsewhere(png_path, entries, engine=None, res=None):
    """How much of what this reader is about to say the OTHER engine read too.

    A chat log is the one view here with no drawing of its own to prove it. A
    tree has Obsidian's guide lines, a terminal has its lattice, a table has
    corridors of blank pixels no row crosses -- a log has only its shape, a
    name and then a message, and a shape is easy to hit by accident. Jared's
    heads-up display hit it: "(same): jong", "=: CONNECTED" and "ror: thers"
    came back as three people talking, from a panel that reads J.A.R.V.I.S
    NEURAL LINK - CONNECTED.

    That was not the recogniser failing to see. It read the panel's stylised
    lettering as best it could and produced words; the other engine, reading
    the same pixels, read something else entirely and shares none of them.
    Where the two agree there is text; where they share nothing there is a
    picture of text, and the reader with the weakest proof of its own is the
    one that should have to show the difference.
    """
    # the pipeline has read this pane with the recogniser already and
    # hands its answer in; reading it again here cost a second pass on
    # every pane the cascade reached
    if res is None:
        if engine is None:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
        res, _ = engine(png_path)
    seen = set(_words(" ".join(t for _, t, _ in (res or []))))
    mine = _words(" ".join(f"{e['who']} {e['said']}" for e in entries))
    if not mine:
        return 0.0
    return sum(1 for w in mine if w in seen) / len(mine)


def read_chat(png_path, engine=None, res=None):
    bgr = machine.pixels(png_path)
    if bgr is None:
        return {"is_chat": False, "why": "could not read the image"}
    small_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    small_mask = note_reader.ink_mask(small_gray)
    bgr = machine.enlarge(bgr, 3)
    big = png_path.replace(".png", "_3x.png")
    machine.write_once(big, bgr, png_path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mask = note_reader.ink_mask(gray)
    rows = [r for r in note_reader.tess_rows(big, gray) if r["text"].strip()]
    rows = split_wide_gaps(rows)
    rows = [r for r in rows if is_text_line(r)]
    rows.sort(key=lambda r: r["y0"])
    if len(rows) < MIN_ENTRIES:
        return {"is_chat": False, "why": "too few lines of text to be a log"}

    heights = [r["y1"] - r["y0"] for r in rows]
    body_h = statistics.median(heights) if heights else 10
    margin = text_margin(rows, body_h)
    # Only the lines that BEGIN at the chat's margin are the chat. The log is
    # drawn over video, and whatever animates behind it leaves marks on other
    # scan lines that survive every other test; they do not share the margin,
    # because nothing arranged them.
    # A word AT the margin, not merely one somewhere to the left of it. The
    # looser test admitted any row beginning further left, which on a frame
    # holding a slide beside a chat let the whole slide into the log: three
    # bullet points and their captions came back as things people had said.
    # Avatars still sit left of the margin and are still stripped, because a
    # line with an avatar has its text at the margin as well.
    rows = [r for r in rows
            if any(abs(w[1] - margin) <= body_h
                   for w in (r.get("words") or []))]
    if len(rows) < MIN_ENTRIES:
        return {"is_chat": False, "why": "no run of lines shares one margin"}
    entries = []
    for r in rows:
        words, had_avatar = strip_avatar(r, margin)
        name, rest = split_name(small_gray, small_mask, r, words, scale=3)
        if had_avatar or not entries:
            entries.append({"who": name, "said": rest,
                            "y0": r["y0"], "y1": r["y1"],
                            "avatar": had_avatar})
        else:
            # a wrapped line of the message above it
            entries[-1]["said"] = entries[-1]["said"].rstrip() + " " + r["text"].lstrip()
            entries[-1]["y1"] = r["y1"]
    entries = [e for e in entries if e["said"].strip() or e["who"]]
    # A speaker's name is a WORD. The Finder sidebar's icons come back as "C)"
    # and "e}" in their own colour at the margin, which is the shape of an
    # avatar and a name, and "Recents Shared Applications Pictures Movies
    # Desktop Documents Downloads iCloud Drive" then read as something someone
    # said. Every real name in the fixture -- ozildartradez, Garden Infuzions,
    # Giwrgos, Michael Taylor -- is letters.
    named = [e for e in entries
             if sum(ch.isalpha() for ch in (e["who"] or "")) >= 2]
    if len(named) < MIN_ENTRIES:
        return {"is_chat": False,
                "why": "no run of entries carries a name in its own colour"}
    # A log is who-said-what, so MOST of its entries carry a speaker. A page
    # of prose does not, and it will still throw up a few by accident: a
    # note's properties panel has field icons in a gutter and labels in their
    # own colour, which is the same shape as an avatar and a name. Measured,
    # the chat gives four names out of four entries and the note four out of
    # twelve.
    if len(named) * 2 <= len(entries):
        return {"is_chat": False,
                "why": (f"only {len(named)} of {len(entries)} entries carry a "
                        "name; a log is who said what")}
    share = confirmed_elsewhere(png_path, entries, engine, res)
    if share < CONFIRMED:
        return {"is_chat": False,
                "why": (f"only {share:.0%} of these words are words the other "
                        "engine read; this is a picture of text, not a log")}
    return {"is_chat": True, "entries": entries}


def render(res):
    if not res.get("is_chat"):
        return f"NOT A CHAT LOG - {res.get('why')}"
    out = []
    for e in res["entries"]:
        who = e["who"] or "(same)"
        out.append(f"{who}: {e['said']}")
    return "\n".join(out)


if __name__ == "__main__":
    print(render(read_chat(sys.argv[1])))
