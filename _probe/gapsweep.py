import sys, os, json
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, panes
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
PICS = {"00:00:00","00:00:10","00:00:30","00:00:50","00:01:00","00:01:20","00:01:30","00:01:40",
        "00:01:50","00:02:20","00:02:50","00:03:00","00:03:30","00:03:50","00:04:00","00:04:10","00:04:40"}
def ink(c):
    if c.size == 0: return 0.0
    return float((cv2.Canny(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), 60, 160) > 0).mean())
meas = {}
for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    ts = m.get("ts")
    if ts not in PICS: continue
    fr = m.get("frame")
    if not fr or not os.path.exists(fr): continue
    img = cv2.imread(fr); Hh, Ww = img.shape[:2]
    quiet = set(m.get("quiet") or [])
    rows = []
    for i, b in enumerate(panes.frame_regions(img) or []):
        if i not in quiet: continue
        x0, y0, x1, y1 = [int(v) for v in b]
        rows.append((i, (x1-x0)*(y1-y0)/float(Hh*Ww), ink(img[y0:y1, x0:x1])))
    meas[ts] = rows
json.dump(meas, open(r"_probe\gapmeas.json", "w"))
WRONG = {"00:00:50","00:01:40","00:03:30","00:04:00"}
print("every quiet region, sorted by how much of the frame it covers:")
allr = sorted(((a, v, ts, i) for ts, rows in meas.items() for i, a, v in rows), reverse=True)
for a, v, ts, i in allr[:12]:
    print("   %-9s pi=%-3d area=%5.1f%%  ink=%.4f  %s" % (ts, i, 100*a, v, "WRONG" if ts in WRONG else "right"))
print("\nsweep -- which moments a line would mark, over a wide range of both bars:")
for amin in (0.02, 0.03, 0.05, 0.07, 0.10):
    for imin in (0.005, 0.008, 0.010, 0.012, 0.015):
        hit = sorted({ts for ts, rows in meas.items() for _, a, v in rows if a >= amin and v >= imin})
        print("   area>=%4.0f%%  ink>=%.3f  ->  %d: %s" % (100*amin, imin, len(hit), " ".join(t[3:] for t in hit)))
