"""Would a shape gate skip panes no reader was ever going to claim?

Reads a finished records file and, for every candidate rule, reports what it
would skip, what it would save, and -- the only number that matters -- how many
panes a reader DID claim it would have thrown away.
"""
import json, sys, collections

path = sys.argv[1] if len(sys.argv) > 1 else \
    "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/records.jsonl"
panes = []
for l in open(path, encoding="utf-8"):
    try: d = json.loads(l)
    except Exception: continue
    pp = dict((int(pi), s) for pi, s in ((d.get("took") or {}).get("per_pane") or []))
    for p in (d.get("panes") or []):
        b = p.get("box")
        if not b or len(b) < 4: continue
        w, h = b[2] - b[0], b[3] - b[1]
        if w <= 0 or h <= 0: continue
        panes.append((w, h, p.get("kind") or "?", pp.get(int(p.get("pi", -1)), 0.0)))
tot = sum(p[3] for p in panes)
print("%d panes with a box, %.0f s of pane time\n" % (len(panes), tot))

by = collections.Counter(); n = collections.Counter()
for w, h, k, s in panes: by[k] += s; n[k] += 1
print("%-24s %5s %9s %8s %7s" % ("what it turned out to be", "panes", "seconds", "each", "share"))
for k, s in by.most_common():
    print("%-24s %5d %9.1f %8.1f %6.0f%%" % (k[:24], n[k], s, s/max(1, n[k]), 100*s/tot))

print("\n%-26s %7s %9s %7s %s" % ("rule", "skips", "saves", "share", "real readings lost"))
def rule(name, test):
    sk = [p for p in panes if test(p[0], p[1])]
    lost = [p for p in sk if p[2] != "text, not a tree"]
    saved = sum(p[3] for p in sk)
    print("%-26s %7d %8.1fs %6.0f%% %s" % (name, len(sk), saved, 100*saved/tot,
          ("%d  %s" % (len(lost), sorted(collections.Counter(p[2] for p in lost).items()))) if lost else "none"))
for px in (150, 200, 250, 300):
    rule("shorter than %d px" % px, lambda w, h, px=px: h < px)
for a in (150, 200, 250, 300, 400, 500):
    rule("area under %dk px" % a, lambda w, h, a=a: w * h < a * 1000)

claimed = [p for p in panes if p[2] not in ("text, not a tree", "?")]
if claimed:
    print("\nthe smallest pane each reader actually claimed:")
    for k in sorted(set(p[2] for p in claimed)):
        v = [p for p in claimed if p[2] == k]
        print("   %-22s min width %4d, min height %4d, MIN AREA %9d"
              % (k, min(x[0] for x in v), min(x[1] for x in v), min(x[0]*x[1] for x in v)))
    print("\n   -> any area rule must sit UNDER %d to lose nothing." % min(x[0]*x[1] for x in claimed))
