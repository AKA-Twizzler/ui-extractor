#!/usr/bin/env python3
"""Read a terminal: the exact text, and what was TYPED against what came back.

    python3 console_reader.py <frame.png>

A terminal is not a document. Read as one it comes back as a wall of prose
with its indentation flattened and no way to tell a command Jared typed from
the output that answered it -- which is most of what a terminal is for.

Three facts about a terminal make it readable more exactly than anything else
on screen, and all three are measurements rather than conventions:

  it is a LATTICE.  Every character sits on the same advance, so the column of
                    any glyph is (its x, less the left margin) over that
                    advance. Spacing therefore comes from GEOMETRY, not from
                    the recogniser's spaces -- which is worth having, because
                    dropped spaces are the one error two engines still share.

  the prompt REPEATS. The same string stands at the start of every line the
                    user typed on, and nowhere else. So the typed lines are
                    the ones that begin with the string that recurs, found by
                    looking rather than by knowing that shells use "$" or "%".

  the font REPEATS.  A terminal draws the same character with the same pixels
                    every time, so a doubted cell can be compared against
                    every other cell on screen. The ones it MATCHES were read
                    too, and what most of them were read as is evidence about
                    this one. That is how "~/.zshre" becomes "~/.zshrc": not
                    by preferring an engine, but because that cell's pixels
                    are the same pixels as four confident "c"s.

Neither of the first two depends on the shell. zsh, bash, a Windows prompt or
Claude Code's own "> " are all a repeated leading string on a lattice.

What it refuses: text whose characters are not all one width is not a
terminal; a word the lattice cannot place stands as the recogniser read it and
nothing may correct it; a cell that matches nothing else on screen keeps its
own reading; and a line reaching the right of the picture is marked, "cut"
where a glyph is visibly bisected and "edge" where it may merely have ended
there. Jared's recordings zoom in on terminals wider than the shot, so that
text is gone for good, and inventing the rest of a command would be the worst
answer available.
"""
import collections
import re
import statistics
import sys

import cv2
import numpy as np

import note_reader
import machine
import verify_names

MONO_SPREAD = 0.04     # character widths vary less than this on a lattice
MIN_PROMPTS = 2        # one line proves no repetition
SAME_GLYPH = 1.5       # a match stands this close, in units of the font's
                       # own repeat distance, measured on the frame itself
GROUP_MIN = 3          # and enough cells on screen for a match to mean it
INK_CELL = 24          # ink in a cell, past what bleeds in from its neighbours
ROW_OFF = 0.10         # how far a line may sit off a whole multiple of the pitch
ROW_SIZE = 0.10        # and how far its own advance may sit off the common one


def normalise(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def advance_of(rows):
    """The width of one character cell, roughly, and how much it varies.

    Only the variation is used as a test: on a lattice every character is one
    width, so a small spread IS the evidence that this is a terminal. The
    width itself is measured properly further down, because a median of word
    widths drifts half a cell by the end of a long word.
    """
    widths = []
    for r in rows:
        for t, x0, x1 in (r.get("words") or []):
            if len(t) >= 3:
                widths.append((x1 - x0) / len(t))
    if len(widths) < 8:
        return None, None
    mid = statistics.median(widths)
    if mid <= 0:
        return None, None
    spread = statistics.median([abs(w - mid) for w in widths]) / mid
    return mid, spread


def beat(profile, lo, hi, span):
    """The period and phase of a run of ink.

    A word box hugs the ink and stops where the letter stops, so it sits
    inside its cell by an amount that depends on WHICH letter it is -- useless
    as an anchor. The pixels themselves are periodic instead: the profile of
    ink down each column beats at the advance, and the cell boundaries fall
    wherever that profile is quietest.
    """
    p = profile[lo:hi + 1].astype(np.float64)
    p = p - p.mean()
    scores = []
    for lag in range(span[0], span[1]):
        a, b = p[:-lag], p[lag:]
        if len(a) < 40:
            break
        denom = np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9
        scores.append((float((a * b).sum() / denom), lag))
    if not scores:
        return None, None
    scores.sort(reverse=True)
    top = scores[0][0]
    if top <= 0:
        return None, None
    # the fundamental, not one of its harmonics: the shortest lag that beats
    # nearly as well as the best one does
    period = float(min(l for c, l in scores if c > top * 0.9))
    full = profile.astype(np.float64)
    best = None
    for cand in np.arange(period - 1.5, period + 1.51, 0.01):
        if cand <= 1:
            continue
        for org in np.arange(lo - cand, lo + 0.001, 0.25):
            ks = np.arange(0, int((hi - org) / cand))
            xs = np.round(org + ks * cand).astype(int)
            xs = xs[(xs >= 0) & (xs < len(full))]
            if not len(xs):
                continue
            quiet = float(full[xs].mean())
            if best is None or quiet < best[0]:
                best = (quiet, float(cand), float(org))
    if best is None:
        return None, None
    return best[1], best[2]


def column_lattice(mask, rows):
    """Where every character cell begins, and how wide it is."""
    prof = np.zeros(mask.shape[1])
    for r in rows:
        prof += mask[r["y0"]:r["y1"], :].sum(axis=0)
    lit = np.nonzero(prof)[0]
    if len(lit) < 40:
        return None, None
    return beat(prof, int(lit.min()), int(lit.max()), (20, 250))


def baseline(mask, row):
    """Where this row's glyphs stand: the sharpest fall in its ink.

    Rows are boxed around their own ascenders and descenders, so their tops
    and bottoms move with whichever letters they happen to hold. The baseline
    does not: most glyphs end on it at once, which makes it the steepest drop
    in the row and the one anchor every row shares. Cells cut on the baseline
    can be compared across rows; cells cut on the box cannot.
    """
    prof = mask[row["y0"]:row["y1"], :].sum(axis=1).astype(float)
    if len(prof) < 4:
        return row["y1"]
    return row["y0"] + int(np.argmin(prof[1:] - prof[:-1])) + 1


def place_words(mask, row, base, adv, org, up, down):
    """Lay this row's words on the lattice, and cut out each letter's cell.

    A word of N characters occupies exactly N cells, so when the recogniser
    returns a different count it has inserted or dropped something, and its
    letters cannot be put on the lattice at all. That word is still written
    out as read -- it is simply not offered as evidence about the font, and
    nothing else on screen may correct it.
    """
    y0, y1 = base - up, base + down
    band = mask[y0:y1, :] if 0 <= y0 < y1 <= mask.shape[0] else None
    runs = ink_runs(band, adv, org, mask.shape[1]) if band is not None else []
    words = []
    for t, x0, x1 in (row.get("words") or []):
        # the MIDDLE of the box, never its edges. An edge sits wherever the
        # first or last glyph happens to begin -- a "%" is drawn wide enough
        # that its box crosses into the cell before it, and reading the column
        # off that edge puts the prompt marker one cell early and eats the
        # space in front of it. The middle of a word of known length gives the
        # column back exactly.
        mid = (x0 + x1) / 2.0
        start = int(round((mid - org) / adv - len(t) / 2.0))
        end = start + len(t) - 1
        run = best_run(runs, start, end)
        if run is not None and len(run) == len(t):
            # a run of written-on cells exactly as long as the word settles it
            # outright: those cells ARE the word, whatever the box says
            start, end = run[0], run[-1]
        elif run is not None and len(t) < len(run):
            # the recogniser drops the bracket a prompt opens with, and a "%"
            # sits close enough to the "~" before it that no blank cell
            # separates them; the word still lies inside that run
            start = min(max(start, run[0]), run[-1] - len(t) + 1)
            end = start + len(t) - 1
        cells = []
        if band is not None and run is not None and len(run) >= len(t):
            for j, ch in enumerate(t):
                cx0 = int(round(org + (start + j) * adv))
                cx1 = cx0 + int(round(adv))
                if cx0 < 0 or cx1 > mask.shape[1]:
                    cells = []
                    break
                cells.append({"char": ch,
                              "patch": band[:, cx0:cx1].astype(np.float32)})
        words.append({"text": t, "col": max(0, start), "cells": cells})
    return words


def ink_runs(band, adv, org, width):
    """The unbroken stretches of written-on cells in a row.

    A word box is drawn round the ink and is a cell too wide as often as not,
    so counting cells from its edges puts a five-letter word in six cells and
    the word goes unplaced. The ink knows better: a word is a run of cells
    with something in them, bounded by the blank cells of the spaces around
    it, and its length is a count rather than a measurement.
    """
    runs, cur, col = [], [], 0
    while True:
        x0 = int(round(org + col * adv))
        x1 = x0 + int(round(adv))
        if x1 > width:
            break
        if x0 >= 0 and band[:, x0:x1].sum() >= INK_CELL:
            cur.append(col)
        elif cur:
            runs.append(cur)
            cur = []
        col += 1
    if cur:
        runs.append(cur)
    return runs


def best_run(runs, start, end):
    """The run of written-on cells this word was drawn in."""
    best, cover = None, 0
    for run in runs:
        overlap = min(run[-1], end) - max(run[0], start) + 1
        if overlap > cover:
            best, cover = run, overlap
    return best


def agree(cells):
    """Let the font settle the letters the recogniser was unsure of.

    Cells whose pixels match are the same character -- a terminal cannot draw
    one glyph two ways. So every cell is compared against every other, and the
    ones that match it vote on what it is.

    "Match" is decided without a distance at all, because every distance that
    would work here is a hair's breadth wide: on this screen two "h"s sit
    0.009 apart and an "h" and an "n" 0.017, so any cut loose enough to catch
    a real pair is one nudge away from calling every "h" an "n". Instead a
    letter is overruled only when the three cells nearest it AGREE -- which a
    glyph drawn once cannot produce, and a glyph confusable with its neighbour
    produces only when the neighbours really are the same glyph.
    """
    usable = [c for c in cells if c["patch"].size]
    if len(usable) < GROUP_MIN * 2:
        return 0
    shape = collections.Counter(
        c["patch"].shape for c in usable).most_common(1)[0][0]
    pool = [c for c in usable if c["patch"].shape == shape]
    if len(pool) < GROUP_MIN * 2:
        return 0
    # at full resolution, and no smaller: shrinking the cells first blurs away
    # the ascender that is the whole difference between "h" and "n", and the
    # two glyphs merge into one group that then votes "n" onto every "h"
    stack = np.stack([c["patch"] for c in pool])
    d = np.empty((len(pool), len(pool)), np.float32)
    for i in range(len(pool)):
        d[i] = np.abs(stack - stack[i]).mean(axis=(1, 2))
    off = d + np.eye(len(pool), dtype=d.dtype) * 9
    # how close this font's own repeats stand: nearly every glyph on a
    # screenful of terminal is drawn more than once, so the typical distance
    # from a cell to its closest twin IS the distance at which the font
    # repeats itself, measured on this frame and no other
    twin = float(np.median(off.min(axis=1)))
    if twin <= 0:
        return 0
    labels = np.array([c["char"] for c in pool], dtype=object)
    fixed = 0
    for i, cell in enumerate(pool):
        j = int(np.argmin(off[i]))
        closest = float(off[i][j])
        if closest > twin * SAME_GLYPH:
            continue                       # nothing on screen looks like it
        win = pool[j]["char"]
        if win == cell["char"]:
            continue
        # and the reading that overrules it must itself appear more than once.
        # A screen carries a few glyphs drawn a single time -- a warning sign,
        # a bullet, a tick -- and left to themselves they match each other,
        # every one of them a lone blob. A reading seen once is exactly as
        # likely to be the mistake as the letter it would replace.
        if int(np.count_nonzero(labels == win)) < 2:
            continue
        # what the recogniser called it must also be on screen somewhere, and
        # further away: a letter is only overruled when the cell it matches
        # stands clearly nearer than the nearest cell read the same way it was
        own = off[i][labels == cell["char"]]
        if len(own) and closest * SAME_GLYPH >= float(own.min()):
            continue
        cell["char"] = win
        fixed += 1
    return fixed


def lay_out(words):
    """Put the row back together at the columns it was drawn at.

    A terminal indents with real characters, and how far a line is indented is
    part of what it says. Rebuilding from the columns keeps that exactly, and
    repairs the spaces the recogniser drops as a free consequence.
    """
    line = ""
    for w in sorted(words, key=lambda w: w["col"]):
        text = "".join(c["char"] for c in w["cells"]) if w["cells"] else w["text"]
        col = w["col"]
        if col < len(line):
            col = len(line) + 1
        line += " " * (col - len(line)) + text
    return line.rstrip()


def runs_off_frame(mask, base, up, down, text, adv, org):
    """Whether the frame cuts this line off, and text is missing to its right.

    Jared's recordings zoom in, so a terminal is often wider than the picture
    and a long line simply leaves the shot. Two things show it, and they are
    not equally strong, so they are not reported as one:

      "cut"   a glyph has ink in the very last column of pixels. The frame
              went through the middle of a letter, so there is certainly more.
      "edge"  the line reaches the last cell the frame can hold. It may have
              ended there and it may not -- a line cut in the space BETWEEN
              two glyphs leaves nothing bisected and looks complete.

    The weaker mark earns its keep: a sentence that happens to end in the last
    column is called doubtful now and then, which costs a note, while a
    command cut in half and presented as whole costs the truth of the screen.
    """
    y0, y1 = base - up, base + down
    if not (0 <= y0 < y1 <= mask.shape[0]):
        return None
    if mask[y0:y1, -2:].any():
        return "cut"
    last_col = int((mask.shape[1] - org) / adv) - 1
    if text and len(text.rstrip()) - 1 >= last_col - 1:
        return "edge"
    return None


def find_prompt(lines):
    """Which lines were typed on, and where the typing starts.

    The prompt is whatever string recurs at the start of more than one line.
    Its tail is the marker -- the one character every one of those lines also
    carries, "%" or "$" or ">" -- and what follows the marker is what was
    typed.
    """
    heads = {}
    for i, ln in enumerate(lines):
        text = ln["text"]
        stripped = text.lstrip()
        if len(text) - len(stripped) > 2 or not stripped:
            continue
        heads.setdefault(normalise(stripped.split()[0]), []).append(i)
    # The recogniser does not read the same prompt the same way twice: the
    # very same host came back as "jared@macbook-air" on one line and
    # "'jJared@macbook-air" on the next, so grouping on exact text splits one
    # prompt into two and loses half the typed lines. Heads where one reading
    # contains the other are the same prompt.
    merged = {}
    for k in sorted(heads, key=len, reverse=True):
        if len(k) < 3:
            merged[k] = list(heads[k])
            continue
        for seen in merged:
            if len(seen) >= 3 and (k in seen or seen in k):
                merged[seen].extend(heads[k])
                break
        else:
            merged[k] = list(heads[k])
    best = sorted(max(merged.values(), key=len)) if merged else []
    if len(best) < MIN_PROMPTS:
        return [], None
    marks = []
    for i in best:
        marks.append({ch for ch in lines[i]["text"]
                      if not ch.isspace() and not ch.isalnum()})
    shared = set.intersection(*marks) if marks else set()
    for cand in "%$>#":
        if cand in shared:
            return best, cand
    return best, (sorted(shared)[0] if shared else None)


def read_console(png_path):
    bgr = cv2.imread(png_path)
    if bgr is None:
        return {"is_console": False, "why": "could not read the image"}
    up = machine.enlarge(bgr, 3)
    big = png_path.replace(".png", "_3x.png")
    cv2.imwrite(big, up)
    gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
    mask = note_reader.ink_mask(gray)
    rows = [r for r in note_reader.tess_rows(big, gray) if r["text"].strip()]
    rows.sort(key=lambda r: r["y0"])
    if len(rows) < 4:
        return {"is_console": False, "why": "too few lines to be a terminal"}

    rough, spread = advance_of(rows)
    if rough is None:
        return {"is_console": False, "why": "too little text to measure a cell"}
    if spread > MONO_SPREAD:
        return {"is_console": False,
                "why": (f"character widths vary by {spread:.3f}; a terminal "
                        "sets every character on one advance")}

    # That spread is measured over every word on the frame at once, so one
    # heading three times the size of the body hides inside it: a slide set in
    # a terminal font -- a title bar with traffic lights, a prompt line, then
    # "what "works" means" in display type -- passed at 0.017 and came back
    # 'rends and nriter real riles'. Whether a row is set in the SAME size is
    # a question about that row, so it is asked of each one.
    #
    #   fixture, a real terminal        0.036 off the common advance
    #   another, camera inset and all   0.052
    #   "what works means" slide        0.345
    #   AI PRIMING slide                0.347
    #   a grid of cards, in mono        1.280
    per_row = [statistics.median(
                   [(x1 - x0) / len(t) for t, x0, x1 in (r.get("words") or [])
                    if len(t) >= 3] or [0])
               for r in rows]
    per_row = [a for a in per_row if a > 0]
    if len(per_row) >= 3:
        one = statistics.median(per_row)
        far = max(per_row, key=lambda a: abs(a - one))
        if abs(far - one) / one > ROW_SIZE:
            return {"is_console": False,
                    "why": (f"one line is set {far / one:.2f} times the size "
                            "of the rest; a terminal has one size")}

    # One advance is not enough on its own. A web page set in a monospace
    # font passes that test and then reads as nonsense, because its heading
    # is three times the size of its body and no single lattice fits both.
    # A terminal sets every LINE on one pitch too, so the gaps between its
    # rows are whole multiples of one number -- blank lines make twos and
    # threes, never one-and-a-halves. Measured: a terminal's gaps sit 0.05 of
    # a pitch off a whole multiple, a monospace web page 0.14, a note 0.28.
    tops = sorted(r["y0"] for r in rows)
    gaps = [b - a for a, b in zip(tops, tops[1:]) if b > a]
    if len(gaps) >= 3:
        pitch = min(gaps)
        off = statistics.median([abs(g / pitch - round(g / pitch))
                                 for g in gaps])
        if off > ROW_OFF:
            return {"is_console": False,
                    "why": (f"its lines sit {off:.2f} of a pitch off a whole "
                            "multiple; a terminal's lines are one pitch apart")}

    adv, org = column_lattice(mask, rows)
    if adv is None:
        return {"is_console": False, "why": "no repeating character pitch"}

    gaps = [rows[i + 1]["y0"] - rows[i]["y0"] for i in range(len(rows) - 1)]
    pitch = min([g for g in gaps if g > 0], default=int(rough * 2))
    up_px, down_px = int(pitch * 0.80), int(pitch * 0.25)

    # a line touching the top or bottom of the frame still has a cell band --
    # it simply runs past the picture into blank paper, which is what the
    # terminal has there anyway. Without this the first line of a full-height
    # terminal is the one line nothing can correct.
    padded = np.pad(mask, ((up_px, down_px), (0, 0)))
    laid = []
    for r in rows:
        base = baseline(mask, r)
        laid.append({"row": r, "base": base,
                     "words": place_words(padded, r, base + up_px, adv, org,
                                          up_px, down_px)})
    fixed = agree([c for e in laid for w in e["words"] for c in w["cells"]])

    # The lattice reading and the line engine's reading are two readings of
    # the same pixels, and only one of them was ever printed. On a real
    # terminal the lattice wins -- that is what the fixture measures, 94.2%
    # against 92.2% with the font consensus off. On a slide SET in a terminal
    # font it loses badly, and said so nowhere:
    #
    #   line engine  'PRIMED. NOW do the thing.'   'opal & oak x 22k'
    #   lattice      'PRIMED. NOW do tIe thiII.'   'opaa   « oak x 22k'
    #
    # The build's rule is that a string enters the record only when the
    # instruments confirm it. The lattice's text is kept, because its spacing
    # is the column structure and merging would destroy it, but a line whose
    # LETTERS the two engines read differently is marked and both are shown.
    # Spacing and symbols do not count: the line engine reads a curly quote for
    # the "[" that opens every prompt, and that is settled, not disputed.
    lines = []
    for e in laid:
        text = lay_out(e["words"])
        _, status = verify_names.reconcile(text, e["row"]["text"])
        lines.append({"text": text,
                      "y0": e["row"]["y0"], "y1": e["row"]["y1"],
                      "second": e["row"]["text"],
                      "unsettled": status == "uncertain",
                      "clipped": runs_off_frame(mask, e["base"], up_px,
                                                down_px, text, adv, org)})

    typed_idx, marker = find_prompt(lines)
    typed = set(typed_idx)
    out = []
    for i, ln in enumerate(lines):
        entry = {"text": ln["text"], "clipped": ln["clipped"],
                 "second": ln["second"], "unsettled": ln["unsettled"],
                 "prompt": None, "kind": "output"}
        if i in typed and marker:
            cut = ln["text"].rfind(marker)
            if cut >= 0:
                entry["prompt"] = ln["text"][:cut + 1].strip()
                entry["text"] = ln["text"][cut + 1:].strip()
            entry["kind"] = "typed"
        out.append(entry)
    return {"is_console": True, "advance": adv, "spread": spread,
            "origin": org, "marker": marker, "fixed": fixed, "lines": out}


def render(res):
    if not res.get("is_console"):
        return f"NOT A TERMINAL - {res.get('why')}"
    out = []
    for ln in res["lines"]:
        body = ln["text"]
        if ln["clipped"] == "cut":
            body += "  <the frame cuts this line off here>"
        elif ln["clipped"] == "edge":
            body += "  <reaches the edge of the frame; there may be more>"
        if ln.get("unsettled"):
            body += f"   <- the other engine read {ln['second']!r}"
        if ln["kind"] == "typed":
            out.append(f"$ {body}" if ln["text"] else "$")
        else:
            out.append(f"  {body}")
    return "\n".join(out)


if __name__ == "__main__":
    r = read_console(sys.argv[1])
    if r.get("is_console"):
        print(f"cell {r['advance']:.2f}px from x{r['origin']:.1f}, widths vary "
              f"{r['spread']:.3f}, prompt marker {r['marker']!r}; the font "
              f"settled {r['fixed']} letters\n")
    print(render(r))
