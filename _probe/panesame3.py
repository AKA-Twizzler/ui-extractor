"""How ALIKE must two panes be before their readings are certainly the same?

The first try shrank a pane to a 64x64 thumbnail and called near-matches the
same: 62 of its 67 matches said different things. A thumbnail cannot tell two
pages of text apart. So the question is asked properly -- at FULL resolution,
across a range of strictnesses -- and for each one every match has its recorded
text set against its twin's. The strictness where wrong answers reach zero is
the only one worth having, and what it saves is the answer.
"""
import json, io, os, collections
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

panes = []
for ts, pi, path in order:
    if not path:
        continue
    p = path if os.path.isabs(path) else os.path.join(IMG, os.path.basename(path))
    im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if im is not None:
        panes.append((ts, pi, im, took.get((ts, pi), 0.0)))
print("%d panes with a picture" % len(panes))

for tol in (0.0, 0.5, 1.0, 2.0, 4.0, 8.0):
    seen, hits, wrong, hit_s, all_s = [], 0, 0, 0.0, 0.0
    for ts, pi, im, secs in panes:
        all_s += secs
        twin = None
        for im2, t2 in seen:
            if im2.shape != im.shape:
                continue
            if float(np.mean(np.abs(im2.astype(np.int16) - im.astype(np.int16)))) <= tol:
                twin = t2
                break
        if twin:
            hits += 1
            hit_s += secs
            if text.get((ts, pi), "") != text.get(twin, ""):
                wrong += 1
        else:
            seen.append((im, (ts, pi)))
    print("  within %.1f grey levels a pixel: %3d panes matched, %5.0f s of %5.0f s (%2.0f%%), %d say something different"
          % (tol, hits, hit_s, all_s, 100 * hit_s / max(1, all_s), wrong))
