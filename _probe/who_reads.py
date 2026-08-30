"""Does anything ever ask a STRETCH for a moment the stretch does not cover?
That is the only way the deleted line could have mattered."""
import sys, io, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3
draw3.PROBE = []
real_slice = draw3.state_slice
made = []
def watched(st, t0, t1):
    out = real_slice(st, t0, t1)
    if out is not None:
        made.append(out)
    return out
draw3.state_slice = watched
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
P = draw3.PROBE
print("reads of a per-moment field through .get():", len(P))
miss = [r for r in P if not r[2]]
print("  answered from the moment itself:", len(P) - len(miss))
print("  MISSES (no record for that moment):", len(miss))
from collections import Counter
print("  misses by field:", dict(Counter(f for f, _, _, _ in miss)))
outside = [r for r in miss if r[3] and (r[1] < min(r[3]) or r[1] > max(r[3]))]
print("  of those, asked for a moment OUTSIDE the holder's own stretch:", len(outside))
for r in outside[:8]:
    print("     %-9s asked %s, holder covers %s..%s" % (r[0], r[1], min(r[3]), max(r[3])))
print("slices built:", len(made))
