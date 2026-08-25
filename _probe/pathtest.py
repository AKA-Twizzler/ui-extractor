import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3, selfcheck
note = r"/home/trism/.claude/jobs/014c964f/tmp/replay\_probe\rig\mem72.md"
imgs = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
print("draw3.note:", callable(draw3.note))
f = selfcheck.check(note, imgs)
print("faults:", len(f))
for r, w, x in f[:5]:
    print("  ", r, w, x)
