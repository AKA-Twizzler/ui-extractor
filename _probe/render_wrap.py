"""Render chosen cards and pictures of a note the way the vault shows them
(compare.py's page, headless Edge), one PNG each, to look at."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compare_wrap as compare
note, out = sys.argv[1], sys.argv[2]
pats = sys.argv[3:]
lines = open(note, encoding="utf-8").read().split("\n")
cells, names = [], []
for pat in pats:
    for i, ln in enumerate(lines):
        if ln.startswith("#") and pat in ln:
            j = i + 1
            while j < len(lines) and not lines[j].startswith("<div"):
                j += 1
            cells.append(lines[j]); names.append(re.sub(r"[^A-Za-z0-9]+", "-", pat)[:40]); break
css = open(compare.CSS_PATH, encoding="utf-8").read()
os.makedirs(out, exist_ok=True)
ims = compare.render_page(out, "bits", cells, 1500, css, scale=1)
for im, nm in zip(ims, names):
    im = compare.trim(im); im.save(os.path.join(out, nm + ".png")); print(nm, im.size)
