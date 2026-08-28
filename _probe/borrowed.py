import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
b = draw3.BORROWED
print("shapes answered from ANOTHER MOMENT: %d, across %d moments" % (sum(b.values()), len(b)))
for ts, n in sorted(b.items()):
    print("   %s  x%d" % (ts, n))
