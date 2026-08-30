"""Is a QUIET pane blank wallpaper, or content that could not be read?
The record calls both of them the same thing, which is the whole question."""
import sys, os, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import cv2, numpy as np, panes
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
WANT = {"00:00:10", "00:00:30", "00:04:00", "00:00:50", "00:00:00"}
RIGHT = {"00:00:10", "00:00:30", "00:00:00"}

def ink(crop):
    """share of the box carrying edges -- text and window furniture both"""
    if crop.size == 0: return 0.0
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    e = cv2.Canny(g, 60, 160)
    return float((e > 0).mean())

for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    ts = m.get("ts")
    if ts not in WANT: continue
    fr = m.get("frame")
    if not fr or not os.path.exists(fr):
        print("%s: no frame on disk (%s)" % (ts, fr)); continue
    img = cv2.imread(fr)
    regions = panes.frame_regions(img) or []
    quiet = set(m.get("quiet") or [])
    read = {p.get("pi"): p for p in (m.get("panes") or [])}
    print("=== %s   %s   regions=%d  quiet=%s" % (ts, "RIGHT" if ts in RIGHT else "WRONG", len(regions), sorted(quiet)))
    for i, b in enumerate(regions):
        x0, y0, x1, y1 = [int(v) for v in b]
        v = ink(img[y0:y1, x0:x1])
        tag = "QUIET" if i in quiet else ("read " if i in read else "  -  ")
        area = (x1 - x0) * (y1 - y0) / float(img.shape[0] * img.shape[1])
        print("   %-5s pi=%-3d ink=%5.3f  area=%4.1f%%  box=%s" % (tag, i, v, 100 * area, [x0, y0, x1, y1]))
