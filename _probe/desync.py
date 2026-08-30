import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3
TABLES = []
real = draw3.Table.__init__
def init(self, *a, **k):
    real(self, *a, **k); TABLES.append(self)
draw3.Table.__init__ = init
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
bad = [t for t in TABLES if len(t.paths) != len(t.path_at)]
print("tables built: %d" % len(TABLES))
print("tables whose two parallel lists DISAGREE in length: %d" % len(bad))
for t in bad[:10]:
    print("   paths=%d path_at=%d  -> zip() keeps %d and silently drops %d readings"
          % (len(t.paths), len(t.path_at), min(len(t.paths), len(t.path_at)),
             abs(len(t.paths) - len(t.path_at))))
    print("      moments held: %s" % (t.path_at,))
    for p in t.paths[:4]:
        print("      reading: %s" % (" > ".join(p),))
