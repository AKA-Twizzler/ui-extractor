# diagC-2: trace every path-mending call that touches the memory window's bar
# through the whole note() pipeline (in-process, nothing written), so the step
# that turns `projects` into `projerts` and drops the long crumb is named by
# caller line number.
import sys, os, re, inspect
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old

REC = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
LOG = []

def interesting(*paths):
    for p in paths:
        if not p: continue
        for c in p:
            s = str(c).lower()
            if s.startswith("proj") or s.startswith("-users") or s == "memory" or s == "memory.md":
                return True
    return False

def caller():
    f = sys._getframe(2)
    return "%s:%d in %s" % (os.path.basename(f.f_code.co_filename), f.f_lineno, f.f_code.co_name)

def wrap(name):
    orig = getattr(draw3, name)
    def w(*a, **k):
        r = orig(*a, **k)
        ins = a[0] if a else None
        if interesting(ins, r if isinstance(r, list) else None):
            same = (list(ins) == list(r)) if isinstance(ins, list) and isinstance(r, list) else None
            LOG.append("%-8s @ %s\n    in : %s\n    oth: %s\n    out: %s%s" % (
                name, caller(), ins, [x for x in a[1:]] if len(a) > 1 else "", r, "" if not same else "   (unchanged)"))
        return r
    w.__name__ = name
    setattr(draw3, name, w)

for n in ("mend_path", "align_crumbs", "end_at_folder", "chain_paths", "unglue"):
    wrap(n)

_h = draw3.harmonise
def harmonise_w(states):
    _h(states)
    for st in states:
        t = st.main_table()
        if st.name == "The Finder window" and t and t.path:
            LOG.append("AFTER harmonise: title=%r times=%s path=%s" % (st.title, st.times, t.path))
draw3.harmonise = harmonise_w

text = draw3.note(REC)
print("\n".join(LOG))
print("=" * 100)
print("note length", len(text))
for m in re.finditer(r'sn-pathbar">(.*?)</div>', text):
    bar = re.sub(r'<[^>]+>', '', m.group(1))
    if "memory" in bar or "projerts" in bar:
        print("PATHBAR @%d: %s" % (m.start(), bar))
