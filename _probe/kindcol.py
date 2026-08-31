"""What does the KIND column actually read as, across the whole record?"""
import json, re, collections
REC = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
kinds = collections.Counter()
for l in open(REC, encoding="utf-8", errors="replace"):
    try: d = json.loads(l)
    except Exception: continue
    for p in (d.get("panes") or []):
        data = p.get("data") or {}
        for r in (data.get("rows") or []):
            cells = r.get("cells") or []
            if len(cells) >= 4 and cells[3].strip():
                kinds[cells[3].strip()] += 1
tot = sum(kinds.values())
print("the last column, %d readings, %d distinct\n" % (tot, len(kinds)))
print("%-40s %6s %6s" % ("reading", "times", "share"))
for k, v in kinds.most_common(22):
    print("%-40s %6d %5.0f%%" % (k[:40], v, 100*v/tot))
cutn = sum(v for k, v in kinds.items() if "..." in k or "\u2026" in k)
print("\ncut short: %d of %d readings (%.0f%%), across %d distinct forms"
      % (cutn, tot, 100*cutn/tot, sum(1 for k in kinds if "..." in k or "\u2026" in k)))
print("\nthe DISTINCT things this column is ever trying to say:")
base = collections.Counter()
for k, v in kinds.items():
    b = re.split(r"\.\.\.|\u2026", k)[0][:6].lower()
    base[b] += v
for b, v in base.most_common(12):
    print("   %-10s %5d" % (b, v))
