import sys, os, re, difflib
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
from draw3 import fold, flat
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
S = draw3.build_states(moments)
bar_at, clock_at, strip_at = draw3.desktop_bar(moments)
H0 = (moments[0].get("size") or [0, 2160])[1]
for st in S:
    draw3.strip_furniture(st, strip_at)
    if draw3.bar_title(st, H0): st.title = None
def df(st):
    d = st.main_doc(); return fold("".join(flat(t) for t, _ in d.lines)) if d and d.lines else ""
named = [(st, df(st)) for st in S if draw3.is_real_window(st.name)]
named = [(st, t) for st, t in named if len(t) >= 40]
for c in S:
    if c.name != "The rest of the screen": continue
    ct = df(c)
    if len(ct) < 12: continue
    for w, wt in named:
        sm = difflib.SequenceMatcher(None, ct, wt, autojunk=False)
        if sm.find_longest_match(0,len(ct),0,len(wt)).size >= 40 or \
           sum(b.size for b in sm.get_matching_blocks())/max(1,len(ct)) >= 0.6:
            c.name = w.name; break
obs = [st for st in S if st.name == "The Obsidian window"]
full = max(obs, key=lambda s: len(getattr(s.main_doc(), "lines", []) or []) + len(getattr(s.tree(), "lines", []) or []))
print("fullest state:", full.times[0], "doc", len(full.main_doc().lines), "tree", len(full.tree().lines))
def lines_of(st, fam):
    m = st.main_doc() if fam == "doc" else st.tree()
    return [fold(flat(t)) for t, _ in (getattr(m, "lines", []) or [])]
fd, ft = lines_of(full, "doc"), lines_of(full, "tree")
def covered(x, pool):
    return any(x and (x in y or y in x) for y in pool if y)
for st in obs:
    if st is full: continue
    d, t = lines_of(st, "doc"), lines_of(st, "tree")
    md = [x for x in d if not covered(x, fd)]
    mt = [x for x in t if not covered(x, ft)]
    print("\nstate %s (%d moments): doc %d lines, tree %d lines" % (st.times[0], len(st.times), len(d), len(t)))
    print("   doc lines the fullest LACKS : %d %s" % (len(md), [x[:50] for x in md]))
    print("   tree lines the fullest LACKS: %d %s" % (len(mt), [x[:30] for x in mt][:12]))
    # long-line evidence for merging
    best = 0
    for x in d + t:
        for y in fd + ft:
            if x and y:
                sm = difflib.SequenceMatcher(None, x, y, autojunk=False)
                best = max(best, sm.find_longest_match(0,len(x),0,len(y)).size)
    print("   longest shared line-run with the fullest: %d chars" % best)
