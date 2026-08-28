"""How many panes reach the drawing with no window, and would CONTAINMENT
place them? Measurement before any rule is written."""
import sys, os, json
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"

def inside(b, r, slack):
    return (b[0] >= r[0] - slack and b[1] >= r[1] - slack
            and b[2] <= r[2] + slack and b[3] <= r[3] + slack)

def overlap(b, r):
    w = min(b[2], r[2]) - max(b[0], r[0]); h = min(b[3], r[3]) - max(b[1], r[1])
    if w <= 0 or h <= 0: return 0.0
    return (w * h) / max(1.0, (b[2] - b[0]) * (b[3] - b[1]))

tot = homeless = placed_1 = placed_many = 0
rows = []
for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    if m.get("kind") != "moment": continue
    wins = m.get("windows") or []
    W = (m.get("size") or [3840])[0]
    slack = 0.01 * W
    panes = m.get("panes") or []
    tot += len(panes)
    for p in panes:
        wi = p.get("wi")
        if wi is not None and any(e.get("wi") == wi for e in wins):
            continue
        homeless += 1
        b = p["box"]
        holds = [i for i, e in enumerate(wins) if e.get("rect") and inside(b, e["rect"], slack)]
        if len(holds) == 1: placed_1 += 1
        elif len(holds) > 1: placed_many += 1
        best = max(((overlap(b, e["rect"]), i) for i, e in enumerate(wins) if e.get("rect")),
                   default=(0.0, None))
        rows.append((m["ts"], p.get("pi"), str(p.get("kind"))[:18], b,
                     len(holds), round(best[0], 2), (b[2]-b[0])*(b[3]-b[1])/float(W*(m.get("size") or [0,2160])[1])))
print("panes in the record:            %d" % tot)
print("panes filed under NO window:    %d" % homeless)
print("  contained in exactly one:     %d" % placed_1)
print("  contained in more than one:   %d" % placed_many)
print("  contained in none:            %d" % (homeless - placed_1 - placed_many))
print("\n%-9s %4s %-19s %5s %6s %6s  %s" % ("moment","pi","kind","holds","overlap","area","box"))
for ts, pi, k, b, h, ov, ar in rows:
    print("%-9s %4s %-19s %5d %6.2f %5.1f%%  %s" % (ts, pi, k, h, ov, 100*ar, b))
