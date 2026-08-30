import sys, os, re, difflib
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
from draw3 import fold, flat
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
all_states = draw3.build_states(moments)
bar_at, clock_at, strip_at = draw3.desktop_bar(moments)
H0 = (moments[0].get("size") or [0, 2160])[1]
for st in all_states:
    draw3.strip_furniture(st, strip_at)
    if draw3.bar_title(st, H0):
        st.title = None
def _doc_fold(st):
    d = st.main_doc()
    return fold("".join(flat(t) for t, _ in d.lines)) if d and d.lines else ""
_named = [(st, _doc_fold(st)) for st in all_states if draw3.is_real_window(st.name)]
_named = [(st, t) for st, t in _named if len(t) >= 40]
for c in all_states:
    if c.name != "The rest of the screen":
        continue
    ct = _doc_fold(c)
    if len(ct) < 12:
        continue
    for w, wt in _named:
        sm = difflib.SequenceMatcher(None, ct, wt, autojunk=False)
        longest = sm.find_longest_match(0, len(ct), 0, len(wt)).size
        frac = sum(b.size for b in sm.get_matching_blocks()) / max(1, len(ct))
        if longest >= 40 or (len(ct) >= 12 and frac >= 0.6):
            c.name = w.name
            break
obs = [st for st in all_states if st.name == "The Obsidian window"]
def _card_words(st_):
    h = st_.window_html() or ""
    return set(x.lower() for x in re.findall(r"[A-Za-z][A-Za-z']{3,}", re.sub(r"<[^>]+>", " ", h)))
def _has_structure(st_):
    h = st_.window_html() or ""
    return ('<div class="sn-tree">' in h and "<div>" in h.split('<div class="sn-tree">')[1][:4000]) or "<tr>" in h
print("OBSIDIAN STATES:", len(obs))
W = {}
for st in obs:
    d, t = st.main_doc(), st.tree()
    W[id(st)] = _card_words(st)
    print("\n times=%s title=%r" % (st.times, st.title))
    print("   parts=%s" % [(q["fam"], q["slot"]) for q in st.parts])
    print("   doc lines=%s  tree lines=%s  has_structure=%s  fragment=%s"
          % (len(getattr(d, "lines", []) or []), len(getattr(t, "lines", []) or []),
             _has_structure(st), st.fragment()))
    print("   card words (%d): %s" % (len(W[id(st)]), sorted(W[id(st)])[:40]))
print("\nshared moments between any two:")
for i in range(len(obs)):
    for j in range(i+1, len(obs)):
        sh = set(obs[i].times) & set(obs[j].times)
        print("   %s x %s -> %s" % (obs[i].times[0], obs[j].times[0], sorted(sh) or "NONE"))
print("\nFOLD TEST (cards section rule) for the fragment state:")
frag = [st for st in obs if st.times == ['00:00:50', '00:01:10']][0]
mine = W[id(frag)]
others = set().union(*[W[id(x)] for x in obs if x is not frag]) or set()
print("   fragment words:", sorted(mine))
print("   in others:", sorted(mine & others))
print("   NOT in others:", sorted(mine - others))
print("   containment = %d/%d = %.3f  (needs >= 0.9)" % (len(mine & others), len(mine), len(mine & others)/max(1,len(mine))))
print("   _has_structure(fragment) =", _has_structure(frag))
