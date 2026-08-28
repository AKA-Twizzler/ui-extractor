import sys, os, json
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, panes
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
PICS = ["00:00:00","00:00:10","00:00:30","00:00:50","00:01:00","00:01:20","00:01:30","00:01:40",
        "00:01:50","00:02:20","00:02:50","00:03:00","00:03:30","00:03:50","00:04:00","00:04:10","00:04:40"]
WRONG = {"00:00:50","00:01:40","00:03:30","00:04:00"}
def ink(c):
    if c.size == 0: return 0.0
    return float((cv2.Canny(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), 60, 160) > 0).mean())
out = []
for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    ts = m.get("ts")
    if ts not in PICS: continue
    fr = m.get("frame")
    if not fr or not os.path.exists(fr): continue
    img = cv2.imread(fr); Hh, Ww = img.shape[:2]
    regions = panes.frame_regions(img) or []
    quiet = set(m.get("quiet") or [])
    blank = inky = 0; worst = 0.0; biggest = None
    for i, b in enumerate(regions):
        if i not in quiet: continue
        x0, y0, x1, y1 = [int(v) for v in b]
        a = (x1-x0)*(y1-y0)/float(Hh*Ww); v = ink(img[y0:y1, x0:x1])
        if v >= 0.010 and a >= 0.05:
            inky += 1
            if a > worst: worst, biggest = a, (i, a, v)
        else:
            blank += 1
    out.append((ts, len(quiet), blank, inky, biggest))
print("%-10s %6s %6s %6s  %-9s %s" % ("moment","quiet","blank","unread","by eye","the biggest region looked at and not read"))
for ts, q, b, u, big in sorted(out):
    d = ("pi=%d  %.0f%% of the frame, ink %.3f" % (big[0], 100*big[1], big[2])) if big else "-"
    print("%-10s %6d %6d %6d  %-9s %s" % (ts, q, b, u, "WRONG" if ts in WRONG else "right", d))
fires = [ts for ts, q, b, u, big in out if u]
print("\na line gated on (area >= 5%% and ink >= 0.010) fires on %d of 17: %s" % (len(fires), " ".join(sorted(fires))))
