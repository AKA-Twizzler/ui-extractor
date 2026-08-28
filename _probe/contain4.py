"""CONTROL. If assigned panes are contained in their own window, the geometry
is 'a window holds its panes' and the leftovers are outside it. If assigned
panes ALSO fail to overlap, my rectangle test is wrong and every number above
is worthless."""
import sys, os, json
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
def area(r): return max(0.0, r[2]-r[0]) * max(0.0, r[3]-r[1])
def inter(a, b):
    w = min(a[2],b[2]) - max(a[0],b[0]); h = min(a[3],b[3]) - max(a[1],b[1])
    return w*h if w > 0 and h > 0 else 0.0
n = inside = touch = none = 0
ex = []
for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    if m.get("kind") != "moment": continue
    wins = {e.get("wi"): e for e in (m.get("windows") or []) if e.get("rect")}
    for p in (m.get("panes") or []):
        e = wins.get(p.get("wi"))
        if e is None: continue
        n += 1
        b, r = p["box"], e["rect"]
        iv = inter(b, r); sp = iv / max(1.0, area(b))
        if sp >= 0.9: inside += 1
        elif iv > 0: touch += 1
        else: none += 1
        if len(ex) < 8: ex.append((m["ts"], p.get("pi"), round(100*sp), b, r))
print("panes filed UNDER a window: %d" % n)
print("   90%%+ of the pane inside that window: %d" % inside)
print("   overlapping but not contained:       %d" % touch)
print("   not touching their own window:       %d" % none)
print("\nfirst few, pane box against its window's box:")
for ts, pi, sp, b, r in ex:
    print("   %-9s pi=%-3s %3d%% inside   pane=%s   window=%s" % (ts, pi, sp, b, r))
