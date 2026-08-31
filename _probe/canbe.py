"""Can a pane be told apart from a LIST before any reader runs?

The list reader is the dearest in the cascade and it fails on most panes: of
136, eighteen are a list of columns. If the ink alone can say "there is no list
here" without ever being wrong about a real one, the reader need not run.

The test is arithmetic: rows of ink evenly pitched down the pane, and the ink
of those rows falling into two or more columns with clear gaps between them.
Every pane in the record is put through it and set against what the reader
actually decided, so a test that would lose a list shows up as a miss.
"""
import json, io, os, sys, collections
import numpy as np, cv2

D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian"
IMG = os.path.join(D, "Images")

def rows_and_columns(im):
    """(how evenly the ink rows are pitched, how many column gaps) from grey."""
    g = im if im.ndim == 2 else cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    if g.shape[0] < 40 or g.shape[1] < 80:
        return 0.0, 0
    med = float(np.median(g))
    ink = np.abs(g.astype(np.int16) - med) > 35
    rows = ink.mean(axis=1) > 0.004
    # the bands of writing, and how evenly they repeat
    bands, run = [], None
    for i, v in enumerate(rows):
        if v and run is None:
            run = i
        elif not v and run is not None:
            if i - run >= 3:
                bands.append((run, i))
            run = None
    if len(bands) < 4:
        return 0.0, 0
    mids = [(a + b) / 2.0 for a, b in bands]
    gaps = np.diff(mids)
    med_gap = float(np.median(gaps))
    even = float(np.mean(np.abs(gaps - med_gap) <= 0.25 * med_gap)) if med_gap > 0 else 0.0
    # the columns: down the pane, stretches with no ink at all
    cols = ink.mean(axis=0) > 0.002
    gapsx, run = 0, None
    for i, v in enumerate(cols):
        if not v and run is None:
            run = i
        elif v and run is not None:
            if i - run >= max(12, ink.shape[1] // 40):
                gapsx += 1
            run = None
    return even, gapsx

seen = []
for line in io.open(os.path.join(D, "records.jsonl"), encoding="utf-8"):
    d = json.loads(line)
    if d.get("kind") != "moment":
        continue
    for p in d.get("panes") or []:
        if p.get("image"):
            seen.append((str(p.get("kind") or "none"), p["image"]))

out = collections.Counter()
detail = collections.defaultdict(list)
for kind, path in seen:
    pth = path if os.path.isabs(path) else os.path.join(IMG, os.path.basename(path))
    im = cv2.imread(pth, cv2.IMREAD_GRAYSCALE)
    if im is None:
        continue
    even, gaps = rows_and_columns(im)
    could = even >= 0.5 and gaps >= 2
    out[(kind, could)] += 1
    detail[kind].append((round(even, 2), gaps))

print("%-24s %8s %8s" % ("what the reader decided", "could", "could not"))
for kind in sorted({k for k, _ in out}):
    print("%-24s %8d %8d" % (kind, out[(kind, True)], out[(kind, False)]))
lists_missed = out[("a list of columns", False)]
saved = sum(v for (k, c), v in out.items() if not c)
print()
print("lists the test would have refused: %d" % lists_missed)
print("panes the list reader need not run on: %d of %d" % (saved, sum(out.values())))
if lists_missed:
    print("the refused lists looked like:", detail["a list of columns"][:8])
