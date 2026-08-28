import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3
T = []
real = draw3.Table.__init__
def init(self, *a, **k):
    real(self, *a, **k); T.append(self)
draw3.Table.__init__ = init
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
print("tables built: %d" % len(T))
print("readings that carry a moment:  %d" % sum(1 for t in T for ts, _ in t.readings if ts))
print("readings with no moment:       %d" % sum(1 for t in T for ts, _ in t.readings if not ts))
copied = [t for t in T if len(t.readings) >= 2]
print("tables holding two or more readings: %d" % len(copied))
for t in copied[:6]:
    print("   %s" % [(ts, " > ".join(p[-2:])) for ts, p in t.readings][:3])
try:
    T[0].paths = [["x"]]
    print("*** a bare list of paths was ACCEPTED — the guard is not a guard")
except Exception as e:
    print("refused: tab.paths = [...] -> %s: %s" % (type(e).__name__, str(e)[:60]))
