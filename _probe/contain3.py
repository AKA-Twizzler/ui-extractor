"""What IS the relationship between a homeless pane and the windows? Asked
both ways round, because containment measured zero and a rule that never
fires is worth understanding before it is replaced."""
import sys, os, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
PICS = {"00:00:00","00:00:10","00:00:30","00:00:50","00:01:00","00:01:20","00:01:30","00:01:40",
        "00:01:50","00:02:20","00:02:50","00:03:00","00:03:30","00:03:50","00:04:00"}
def area(r): return max(0.0, r[2]-r[0]) * max(0.0, r[3]-r[1])
def inter(a, b):
    w = min(a[2],b[2]) - max(a[0],b[0]); h = min(a[3],b[3]) - max(a[1],b[1])
    return w*h if w > 0 and h > 0 else 0.0
kinds = {"pane inside window":0, "window inside pane":0, "they cross":0, "no touch at all":0}
rows = []
for line in open(P, encoding="utf-8"):
    try: m = json.loads(line)
    except Exception: continue
    if m.get("ts") not in PICS: continue
    wins = [e for e in (m.get("windows") or []) if e.get("rect")]
    W, H = (m.get("size") or [3840, 2160])
    for p in (m.get("panes") or []):
        if p.get("wi") is not None and any(e.get("wi") == p.get("wi") for e in wins):
            continue
        b = p["box"]; ab = area(b)
        best = None
        for e in wins:
            r = e["rect"]; iv = inter(b, r)
            if iv <= 0: continue
            sp, sw = iv/max(1.0, ab), iv/max(1.0, area(r))
            if best is None or iv > best[0]: best = (iv, sp, sw, r)
        if best is None:
            kinds["no touch at all"] += 1; rows.append((m["ts"], p.get("pi"), 0.0, 0.0)); continue
        _, sp, sw, r = best
        if sp >= 0.9: kinds["pane inside window"] += 1
        elif sw >= 0.9: kinds["window inside pane"] += 1
        else: kinds["they cross"] += 1
        rows.append((m["ts"], p.get("pi"), sp, sw))
print("homeless panes, by how they sit against the nearest window:")
for k, v in kinds.items(): print("   %-22s %d" % (k, v))
print("\n%-9s %4s %10s %12s" % ("moment","pi","of the pane","of the window"))
for ts, pi, sp, sw in rows[:26]:
    print("%-9s %4s %9.0f%% %11.0f%%" % (ts, pi, 100*sp, 100*sw))
