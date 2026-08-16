#!/usr/bin/env python3
"""The second instrument: check every name with a different recogniser.

One engine's word is not evidence. Each row is read again with tesseract, on
that row's own pixels, and the two readings are reconciled by a rule that
holds for both engines: OCR drops spaces, it does not invent them. So

  identical                 -> confident
  same letters, more spaces -> take the spaced reading, note it was reconciled
  differ only on look-alike -> AMBIGUOUS, undecidable from pixels (capital I
    glyphs                     against lowercase l is the common one)
  different letters         -> UNCERTAIN, both readings kept, nothing chosen

Nothing is silently preferred. A row the two engines disagree on leaves this
module marked uncertain, and it must reach the record marked that way too.
"""
import re
import subprocess
import tempfile
import os

import cv2
import numpy as np
import machine

PAD_Y = 6
UPSCALE = 4
# what the folder arrow turns into when an engine reads it as text
ARROW_JUNK = "~^‘’`'\"|<>»›˃˅⌄▸▾▶▼ "


def _tess_line(img_bgr_gray, psm=7):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        path = fh.name
    try:
        cv2.imwrite(path, img_bgr_gray)
        # encoding: tesseract writes UTF-8 whatever the machine's locale is,
        # and Windows decodes a pipe in cp1252 unless told
        r = subprocess.run(
            [machine.tesseract_or_refuse(), path, "stdout", "-l", "eng",
             "--psm", str(psm)],
            capture_output=True, text=True, encoding="utf-8")
        return " ".join(r.stdout.split())
    finally:
        os.unlink(path)


def read_row(img, row, pad_right=8):
    """Read one row's name strip with the second engine."""
    y0 = max(0, row["y0"] - PAD_Y)
    y1 = min(img.shape[0], row["y1"] + PAD_Y)
    x0 = max(0, row["x0"])
    x1 = min(img.shape[1], row.get("x1", img.shape[1]) + pad_right)
    if y1 - y0 < 4 or x1 - x0 < 4:
        return ""
    crop = img[y0:y1, x0:x1]
    crop = cv2.resize(crop, (crop.shape[1] * UPSCALE, crop.shape[0] * UPSCALE),
                      interpolation=cv2.INTER_LANCZOS4)
    # engines are trained on dark text on light paper, so a dark theme is
    # inverted and a light one is left alone. Which it is comes from the
    # pixels: if the common value is dark, the text is the light minority.
    import numpy as _np
    if float(_np.median(crop)) < 128:
        crop = 255 - crop
    return _tess_line(crop)


ELLIPSES = ("\u2026", "...")


def truncation(name):
    """Split a name the application itself shortened into (head, tail).

    Applications cut names they cannot fit and draw an ellipsis in the gap:
    'project_ship...ation_fix.md'. Those letters were never on the screen, so
    no amount of resolution recovers them from this frame — the only way back
    is another frame where the column was wider. What matters is that such a
    name is never mistaken for the real one, so it is marked here and completed
    later if a fuller reading of the same name turns up.
    """
    for e in ELLIPSES:
        if e in name:
            head, _, tail = name.partition(e)
            return head.strip(), tail.strip()
    return None


def completes(short, full):
    """Does `full` plausibly fill in the gap the application cut out."""
    parts = truncation(short)
    if not parts or truncation(full):
        return False
    head, tail = parts
    return (len(full) > len(head) + len(tail)
            and full.startswith(head) and full.endswith(tail))


def strip_arrow_junk(s):
    """Drop the arrow an engine mistook for punctuation at the start of a name."""
    t = s
    while t and t[0] in ARROW_JUNK:
        t = t[1:]
    return t.strip()


# characters that render identically or near-identically in a UI font, so no
# recogniser can separate them from pixels alone
HOMOGLYPHS = ["Il1|", "O0", "S5", "B8", "Z2", "G6", "il", "vy"]


def same_glyph_class(a, b):
    return any(a in cls and b in cls for cls in HOMOGLYPHS)


def only_homoglyph_diff(a, b):
    """True when two readings differ only where the glyphs are undecidable."""
    if len(a) != len(b) or a == b:
        return False
    diffs = [(x, y) for x, y in zip(a, b) if x != y]
    return bool(diffs) and all(same_glyph_class(x, y) for x, y in diffs)


def letters(s):
    return re.sub(r"[^A-Za-z0-9]", "", s)


def subsequence(small, big):
    """Is every character of `small` present in `big`, in order?"""
    it = iter(big)
    return all(ch in it for ch in small)


def _split_on_letters(text):
    """The letters of a reading, and the run of symbols before each of them."""
    seps, letters_out, run = [], [], ""
    for ch in text:
        if ch.isalnum():
            seps.append(run)
            letters_out.append(ch)
            run = ""
        else:
            run += ch
    return seps, letters_out, run


def merge_readings(a, b):
    """Combine two readings of the same letters, keeping every symbol seen.

    Two engines lose DIFFERENT spaces from the same line -- one writes
    "even ona", the other "evenona ... assessment, so" -- so neither contains
    the other and neither is simply the fuller reading. But an engine drops a
    space and never invents one, so a space either of them saw was really
    drawn. The same holds for a symbol: where one read a rendered arrow and
    the other skipped it, welding two version numbers together, the arrow was
    on the screen.

    So the two are walked in step over the letters they agree on, and at each
    gap the longer run of symbols is kept. Returns None if the letters differ,
    which is a real disagreement and not this function's business.
    """
    sa, la, ta = _split_on_letters(a)
    sb, lb, tb = _split_on_letters(b)
    if la != lb:
        return None, 0
    out, clashes = [], 0
    for x, y, ch in zip(sa, sb, la):
        if x != y and len(x) == len(y):
            # not an omission by either engine but a SUBSTITUTION: one read
            # ">" where the other read the arrow that was really drawn.
            # Nothing here can decide it, so it is counted and reported.
            clashes += 1
        out.append(x if len(x) >= len(y) else y)
        out.append(ch)
    if ta != tb and len(ta) == len(tb):
        clashes += 1
    out.append(ta if len(ta) >= len(tb) else tb)
    return "".join(out), clashes


def reconcile(primary, second):
    """Return (name, status) — status in confident | reconciled | uncertain."""
    p = strip_arrow_junk(" ".join(primary.split()))
    s = strip_arrow_junk(" ".join(second.split()))
    if not s:
        return p, "unverified"
    if p == s:
        return p, "confident"
    if letters(p) == letters(s):
        # Same letters, so the two differ only in spaces and symbols. An
        # engine DROPS a glyph it cannot name and never invents one, so the
        # reading that CONTAINS the other in order is the fuller one and
        # wins -- a lost space, or a rendered arrow one engine skipped,
        # welding "2.1.176" and "2.1.178" into a single number.
        #
        # Length alone is not that test. Where one engine read ">" and the
        # other "→" neither contains the other: that is a substitution, the
        # engines genuinely disagree, and the honest answer is to say so
        # rather than let a tie in character count decide it.
        merged, clashes = merge_readings(p, s)
        if merged is None:
            return p, "reconciled"
        return merged, ("ambiguous-symbol" if clashes else "reconciled")
    if only_homoglyph_diff(letters(p), letters(s)):
        return p, "ambiguous-glyph"
    return p, "uncertain"


def verify(png_path, tree):
    """Add a second reading to every row of a tree read."""
    img = cv2.imread(png_path, cv2.IMREAD_GRAYSCALE)
    for row in tree["rows"]:
        second = read_row(img, row)
        # the second engine sees the chevron too; strip it the same way
        from tree_reader import strip_chevron
        second, _ = strip_chevron(second)
        name, status = reconcile(row["name"], second)
        row["name_primary"] = row["name"]
        row["name_second"] = second
        row["name"] = name
        row["name_status"] = status
        row["truncated"] = truncation(name) is not None
    tree["verified"] = True
    return tree


def _flat(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _terms(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3]


def second_engine_text(png_path, psm=6):
    """Everything the other engine reads on this picture, as one string.

    Enlarged and, on a dark theme, inverted first -- the same treatment every
    other second reading in this build gets. Handed the pane raw, tesseract
    missed half the Clock app's real tab labels and they came back unconfirmed,
    which makes the mark meaningless. The point is to separate text no other
    engine can find from text it simply was not given a fair look at.
    """
    img = cv2.imread(png_path)
    if img is None:
        return ""
    if img.shape[1] < 1600:
        img = cv2.resize(img, (img.shape[1] * 3, img.shape[0] * 3),
                         interpolation=cv2.INTER_LANCZOS4)
    if float(np.median(img)) < 128:
        img = 255 - img
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        work = fh.name
    try:
        cv2.imwrite(work, img)
        r = subprocess.run(
            [machine.tesseract_or_refuse(), work, "stdout", "-l", "eng",
             "--psm", str(psm)],
            capture_output=True, text=True, encoding="utf-8")
        return r.stdout or ""
    finally:
        os.unlink(work)


def confirm_readings(png_path, texts, other_text=None):
    """Which of these readings the OTHER engine read too, and which it did not.

    The build's rule is that a string enters the record only when the
    instruments confirm it, and two paths were breaking it: the fallback that
    prints whatever one engine read off a pane it could not otherwise place,
    and the panel reader. Both stated their readings as fact.

    That is how "R78" came to be printed off Jared's visualizer. Something IS
    drawn there -- three faint marks on near-black, read at 0.65 where the
    same panel's other labels read at 0.86 -- and the other engine, on the
    same pixels, finds nothing of it. Neither "R78" nor "there is no R78" is
    the truth; "one engine read R78 and nothing confirms it" is.

    So nothing is dropped and nothing is asserted: each reading comes back
    with whether it was confirmed, and the caller says so plainly.

    `other_text` is for the callers whose FIRST engine is tesseract -- the
    panel reader is one -- so the check runs the other way round with whatever
    the other engine read on the same pixels.
    """
    other = second_engine_text(png_path) if other_text is None else other_text
    flat, terms = _flat(other), set(_terms(other))
    out = []
    for text in texts:
        mine, words = _flat(text), _terms(text)
        ok = bool(mine) and len(mine) >= 3 and mine in flat
        if not ok and words:
            ok = sum(1 for w in words if w in terms) * 2 >= len(words)
        out.append((text, ok))
    return out


if __name__ == "__main__":
    import sys, json
    from tree_reader import read_tree, render
    png = sys.argv[1]
    t = verify(png, read_tree(png))
    print(render(t))
    print()
    for r in t["rows"]:
        if r["name_status"] not in ("confident",):
            print(f"  [{r['name_status']:11s}] {r['name_primary']!r} | {r['name_second']!r}")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump(t, open(out, "w"), indent=2)
        print(f"\nwrote {out}")
