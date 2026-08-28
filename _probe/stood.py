"""Does asking for the moment BEFORE ever differ from taking whichever moment
ran last? If it never differs, the change is cosmetic and I should say so."""
import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3

calls = {"n": 0, "differ": 0, "old_none_new_some": 0, "old_some_new_none": 0}
real = draw3.State.stood_before
shadow = {}          # id(state) -> the last stood written, the OLD rule

def watched(self, ts):
    new = real(self, ts)
    old = shadow.get(id(self))
    calls["n"] += 1
    if old is None and new is not None: calls["old_none_new_some"] += 1
    elif old is not None and new is None: calls["old_some_new_none"] += 1
    elif old is not new: calls["differ"] += 1
    return new
draw3.State.stood_before = watched

real_at = draw3.State.at
def at_watch(self, ts, make=False):
    sn = real_at(self, ts, make)
    return sn
draw3.State.at = at_watch

# shadow the OLD rule: every write of .stood also records "the last one written"
real_seen_set = draw3.Seen.__setattr__
def seen_set(self, k, v):
    real_seen_set(self, k, v)
    if k == "stood" and v is not None:
        for st in LIVE:
            if self.ts in st._seen and st._seen[self.ts] is self:
                shadow[id(st)] = v
                break
LIVE = []
real_init = draw3.State.__init__
def init(self, group, ts):
    real_init(self, group, ts)
    LIVE.append(self)
draw3.State.__init__ = init
draw3.Seen.__setattr__ = seen_set

draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
print("stood_before called: %d" % calls["n"])
print("  old rule had nothing, new rule found a moment before: %d" % calls["old_none_new_some"])
print("  old rule had something, new rule has none:            %d" % calls["old_some_new_none"])
print("  both had one and they are DIFFERENT records:          %d" % calls["differ"])
tot = calls["old_none_new_some"] + calls["old_some_new_none"] + calls["differ"]
print("  => the two rules disagree %d times of %d" % (tot, calls["n"]))
