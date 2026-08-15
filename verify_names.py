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

PAD_Y = 6
UPSCALE = 4
# what the folder arrow turns into when an engine reads it as text
ARROW_JUNK = "~^‘’`'\"|<>»›˃˅⌄▸▾▶▼ "


def _tess_line(img_bgr_gray, psm=7):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
        path = fh.name
    try:
        cv2.imwrite(path, img_bgr_gray)
        r = subprocess.run(
            ["tesseract", path, "stdout", "-l", "eng", "--psm", str(psm)],
            capture_output=True, text=True)
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
    # dark theme: engines are trained on dark text on light paper
    crop = 255 - crop
    return _tess_line(crop)


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


def reconcile(primary, second):
    """Return (name, status) — status in confident | reconciled | uncertain."""
    p = strip_arrow_junk(" ".join(primary.split()))
    s = strip_arrow_junk(" ".join(second.split()))
    if not s:
        return p, "unverified"
    if p == s:
        return p, "confident"
    if letters(p) == letters(s):
        return (s, "reconciled") if s.count(" ") > p.count(" ") else (p, "reconciled")
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
    tree["verified"] = True
    return tree


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
