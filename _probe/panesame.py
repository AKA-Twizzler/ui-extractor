"""How much of the READ is reading a pane the video has already shown?

The read reuses a pane only from the moment IMMEDIATELY before, and only when
its rectangle is identical and neither frame was moving. A video shows one
window for a minute at a time, so the question is what a memory with no such
conditions would save. Each pane is fingerprinted by its own pixels -- greyed,
shrunk to a fixed 64 x 64, quantised -- and set against every pane before it.
The seconds come from the record's own per-pane stopwatch.
"""
import json, io, os, sys, collections
import numpy as np, cv2

D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian"
IMG = os.path.join(D, "Images")

took = {}
order = []
for line in io.open(os.path.join(D, "records.jsonl"), encoding="utf-8"):
    d = json.loads(line)
    if d.get("kind") != "moment":
        continue
    for pi, secs in ((d.get("took") or {}).get("per_pane") or []):
        took[(d["ts"], pi)] = float(secs)
    for p in d.get("panes") or []:
        order.append((d["ts"], p.get("pi"), p.get("image"), p.get("same_as") is not None))

def key(path):
    im = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if im is None:
        return None
    g = cv2.resize(im, (64, 64), interpolation=cv2.INTER_AREA)
    return (g // 8).astype(np.uint8)

seen = []          # (fingerprint, ts, pi)
hit_secs = miss_secs = 0.0
hits = misses = 0
for ts, pi, path, was_same in order:
    if not path:
        continue
    p = path if os.path.isabs(path) else os.path.join(IMG, os.path.basename(path))
    k = key(p)
    if k is None:
        continue
    secs = took.get((ts, pi), 0.0)
    twin = None
    for k2, ts2, pi2 in seen:
        if k2.shape == k.shape and np.mean(np.abs(k2.astype(np.int16) - k.astype(np.int16))) <= 0.5:
            twin = (ts2, pi2)
            break
    if twin:
        hits += 1
        hit_secs += secs
    else:
        misses += 1
        miss_secs += secs
        seen.append((k, ts, pi))
print("panes with a picture on disk: %d" % (hits + misses))
print("  already shown earlier: %d  (%.0f s of reading)" % (hits, hit_secs))
print("  new                  : %d  (%.0f s of reading)" % (misses, miss_secs))
if hit_secs + miss_secs:
    print("  a memory with no conditions would save %.0f%% of the pane reading"
          % (100 * hit_secs / (hit_secs + miss_secs)))
