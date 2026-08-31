"""How many cells read across the whole video are the SAME PIXELS as one
already read? Three keys, weakest to strongest, so the answer is honest:
  exact  -- the crop's bytes
  norm   -- the crop greyed, shrunk to 16 rows tall, quantised to 16 levels
  text   -- the reading itself (the ceiling: what a perfect key could save)
Any key that hands back a DIFFERENT reading for the same fingerprint is a
wrong answer and is counted, because a fast wrong answer is worse than none.
"""
import json, glob, os, sys, hashlib, collections
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfirst

IMG = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
HERE_ = os.path.dirname(os.path.abspath(__file__))
CACHE = next((d for d in (os.path.join(HERE_, "pixfirst-cache.warm"),
                          os.path.join(HERE_, "pixfirst-cache"))
              if os.path.isdir(d)), os.path.join(HERE_, "pixfirst-cache"))

frames = {}
def frame(name):
    if name not in frames:
        frames[name] = cv2.imread(os.path.join(IMG, name), cv2.IMREAD_COLOR)
    return frames[name]

def norm_key(c):
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (max(4, int(g.shape[1] * 16 / float(g.shape[0]))), 16),
                   interpolation=cv2.INTER_AREA)
    return hashlib.sha1((g // 16).astype(np.uint8).tobytes()).hexdigest()

seen = {"exact": {}, "norm": {}, "text": {}}
tot = 0
clash = collections.Counter()
for f in sorted(glob.glob(os.path.join(CACHE, "*.json"))):
    r = json.load(open(f, encoding="utf-8"))
    im = frame(r["frame"])
    cols, win = r.get("columns") or [], r.get("window") or []
    if im is None or len(cols) < 2 or len(win) != 4:
        continue
    edges = [int(c[0]) for c in cols] + [int(win[2])]
    for row in r.get("rows") or []:
        ya, yb = int(row["y"][0]), int(row["y"][1])
        for i, txt in enumerate(row.get("cells") or []):
            txt = (txt or "").strip()
            if i + 1 >= len(edges) or not txt:
                continue
            got = pixfirst._cell_crop(im, ya, yb, edges[i], edges[i + 1], i == 0)
            if got is None:
                continue
            crop = np.ascontiguousarray(got[0])
            tot += 1
            for key, val in (("exact", hashlib.sha1(crop.tobytes()).hexdigest()),
                             ("norm", norm_key(crop)),
                             ("text", "%d|%s" % (i, txt))):
                k = (i, val)
                if k in seen[key] and seen[key][k] != txt:
                    clash[key] += 1
                seen[key].setdefault(k, txt)

print("cells cropped: %d  (from %d cached panes)" % (tot, len(glob.glob(os.path.join(CACHE, "*.json")))))
for key in ("exact", "norm", "text"):
    d = len(seen[key])
    print("  %-6s distinct %4d  -> %2.0f%% of reads skippable   wrong answers: %d"
          % (key, d, 100 * (1 - d / float(max(1, tot))), clash[key]))
