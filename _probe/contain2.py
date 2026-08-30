"""Do the windows the DRAWING measures off the frame contain the panes that
arrive with no window? Asked before and after Root 2's three lines."""
import sys, os, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import shapes
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
PICS = {"00:00:00","00:00:10","00:00:30","00:00:50","00:01:00","00:01:20","00:01:30","00:01:40",
        "00:01:50","00:02:20","00:02:50","00:03:00","00:03:30","00:03:50","00:04:00","00:04:10","00:04:40"}
def inside(b, r, s):
    return b[0] >= r[0]-s and b[1] >= r[1]-s and b[2] <= r[2]+s and b[3] <= r[3]+s
tot = held = 0
print("%-9s %7s %7s %8s %9s" % ("moment","panes","no win","frame win","now held"))
for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    if m.get("ts") not in PICS: continue
    wins = m.get("windows") or []
    fr = m.get("frame")
    if not fr or not os.path.exists(fr): continue
    got = shapes.windows(fr) or []
    W, H = (m.get("size") or [3840, 2160])
    s = 0.01 * W
    homeless = [p for p in (m.get("panes") or [])
                if p.get("wi") is None or not any(e.get("wi") == p.get("wi") for e in wins)]
    h = sum(1 for p in homeless if any(inside(p["box"], r, s) for r in got))
    tot += len(homeless); held += h
    print("%-9s %7d %7d %8d %9d" % (m["ts"], len(m.get("panes") or []), len(homeless), len(got), h))
print("\npanes with no window: %d   of those held by a window the DRAWING measures: %d" % (tot, held))
