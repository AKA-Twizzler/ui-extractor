"""Would a pane memory ever hand back the wrong reading?

Three keys, and for each one every pane matched to an earlier twin has its
RECORDED TEXT set against that twin's. A key that pairs two panes saying
different things is a key that would put one window's words in another's.
"""
import json, io, os, hashlib
import numpy as np, cv2

D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian"
IMG = os.path.join(D, "Images")
took, text, order = {}, {}, []
for line in io.open(os.path.join(D, "records.jsonl"), encoding="utf-8"):
    d = json.loads(line)
    if d.get("kind") != "moment":
        continue
    for pi, secs in ((d.get("took") or {}).get("per_pane") or []):
        took[(d["ts"], pi)] = float(secs)
    for p in d.get("panes") or []:
        k = (d["ts"], p.get("pi"))
        text[k] = "\n".join(str(l) for l in (p.get("lines") or []))
        order.append((d["ts"], p.get("pi"), p.get("image")))

def load(path):
    return cv2.imread(path, cv2.IMREAD_GRAYSCALE)

def k_exact(im):
    return hashlib.sha1(np.ascontiguousarray(im).tobytes()).hexdigest() + "|%dx%d" % im.shape[:2]

def k_shrunk(im):
    g = cv2.resize(im, (64, 64), interpolation=cv2.INTER_AREA)
    return (g // 8).astype(np.uint8)

for name in ("exact bytes", "shrunk to 64x64"):
    seen, hits, wrong, hit_s, all_s = {}, 0, 0, 0.0, 0.0
    seen_l = []
    for ts, pi, path in order:
        if not path:
            continue
        p = path if os.path.isabs(path) else os.path.join(IMG, os.path.basename(path))
        im = load(p)
        if im is None:
            continue
        secs = took.get((ts, pi), 0.0)
        all_s += secs
        twin = None
        if name == "exact bytes":
            kk = k_exact(im)
            twin = seen.get(kk)
            if twin is None:
                seen[kk] = (ts, pi)
        else:
            kk = k_shrunk(im)
            for k2, t2 in seen_l:
                if k2.shape == kk.shape and np.mean(np.abs(k2.astype(np.int16) - kk.astype(np.int16))) <= 0.5:
                    twin = t2
                    break
            if twin is None:
                seen_l.append((kk, (ts, pi)))
        if twin:
            hits += 1
            hit_s += secs
            if text.get((ts, pi), "") != text.get(twin, ""):
                wrong += 1
    print("%-18s  %3d panes matched, %5.0f s of %5.0f s (%2.0f%%), and %d of them say something different"
          % (name, hits, hit_s, all_s, 100 * hit_s / max(1, all_s), wrong))
