import sys, glob, os, re, statistics
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import numpy as np
import tree_reader as T

sweep = r"G:\Images\_sweep"
PANE = re.compile(r"\[pane (\d+): a file tree\]")

want = []
for f in sorted(glob.glob(os.path.join(sweep, "*.txt"))):
    vid = os.path.basename(f)[:-4]
    moment = None
    for ln in open(f, encoding="utf-8", errors="replace"):
        if ln.startswith("--- "):
            moment = ln.split()[1]
        m = PANE.search(ln)
        if m and moment:
            png = os.path.join(r"G:\Images", vid,
                               moment.replace(":", "-") + "_pane%s.png" % m.group(1))
            if os.path.exists(png):
                want.append((vid, moment, m.group(1), png))

print("%d panes the library called a file tree" % len(want))
flipped = []
for vid, moment, pi, png in want:
    try:
        t = T.read_tree(png)
    except Exception as e:
        print("  ERROR %s %s pane%s: %s" % (vid, moment, pi, e))
        continue
    if not t.get("is_tree"):
        flipped.append((vid, moment, pi, png, t.get("layout_verdict")))

print("  still trees: %d   now refused: %d" % (len(want) - len(flipped), len(flipped)))
print()
for vid, moment, pi, png, why in flipped:
    print("=" * 72)
    print("%s  %s  pane%s" % (vid, moment, pi))
    print("  %s" % png)
    print("  refused: %s" % why)
    # re-read with the new gate disabled, to show what it WOULD have said
    real = T.looks_like_a_tree
    T.looks_like_a_tree = lambda *a, **k: (True, "forced")
    try:
        old = T.read_tree(png)
    finally:
        T.looks_like_a_tree = real
    rows = old["rows"]
    print("  it used to say:")
    for ln in T.render(old).splitlines()[:12]:
        print("      %s" % ln)
    if len(rows) > 12:
        print("      ... %d more" % (len(rows) - 12))
    x = [r["x0"] for r in rows]
    d = [r["depth"] for r in rows]
    print("  depths %s" % d[:20])
    print("  name x0 %s" % x[:20])
    print("  guide columns %s" % (old.get("guide_columns"),))
