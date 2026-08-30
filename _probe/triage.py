import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sweep
tally = {}
for p in sorted(glob.glob(os.path.join(sweep.OUT, "*.txt"))):
    bad = sweep.smells(open(p, encoding="utf-8").read())
    name = os.path.basename(p)[:-4]
    print(f"{'ok  ' if not bad else str(len(bad)).ljust(4)}{name}")
    for k, d in bad[:10]:
        tally[k] = tally.get(k, 0) + 1
        print(f"      {k:<14} {d}")
    if len(bad) > 10:
        print(f"      ... and {len(bad)-10} more")
print("\ntotals:", tally)
