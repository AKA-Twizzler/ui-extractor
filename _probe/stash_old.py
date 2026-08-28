import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3
LIVE = []
real_init = draw3.State.__init__
def init(self, group, ts):
    real_init(self, group, ts); LIVE.append(self)
draw3.State.__init__ = init
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
h1 = [st for st in LIVE if getattr(st, "_h1_read", None)]
dw = [st for st in LIVE if getattr(st, "_doc_wide_at", None)]
print("OLD build -- headings stashed (_h1_read): %d states, %d readings"
      % (len(h1), sum(len(st._h1_read) for st in h1)))
print("OLD build -- note width stashed:          %d states, %d readings"
      % (len(dw), sum(len(st._doc_wide_at) for st in dw)))
