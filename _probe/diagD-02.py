import sys, os, re, difflib
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw2, draw as old
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
    if not d or not d.lines:
        return ""
    return fold("".join(flat(t) for t, _ in d.lines))
_named = [(st, _doc_fold(st)) for st in all_states if draw3.is_real_window(st.name)]
_named = [(st, t) for st, t in _named if len(t) >= 40]
print("NAMED witnesses:", [(w.name, w.times[0], len(t)) for w, t in _named])
for i, c in enumerate(all_states):
    if c.name != "The rest of the screen":
        continue
    ct = _doc_fold(c)
    print("REST state", i, c.times, "doc_fold len", len(ct), repr(ct[:80]))
    if len(ct) < 12:
        continue
    for w, wt in _named:
        sm = difflib.SequenceMatcher(None, ct, wt, autojunk=False)
        longest = sm.find_longest_match(0, len(ct), 0, len(wt)).size
        frac = sum(b.size for b in sm.get_matching_blocks()) / max(1, len(ct))
        print("    vs", w.name, w.times[0], "longest=%d frac=%.2f -> %s" % (longest, frac, "RENAME" if (longest >= 40 or (len(ct) >= 12 and frac >= 0.6)) else "no"))
        if longest >= 40 or (len(ct) >= 12 and frac >= 0.6):
            c.name = w.name
            break
states = [st for st in all_states if st.window_html() and not st.fragment()]
frags = [st for st in all_states if st not in states and st.has_content() and st.rects]
print("states kept:", len(states), "frags:", len(frags))
def _card_words(st_):
    h = st_.window_html() or ""
    return set(x.lower() for x in re.findall(r"[A-Za-z][A-Za-z']{3,}", re.sub(r"<[^>]+>", " ", h)))
def _has_structure(st_):
    h = st_.window_html() or ""
    return ('<div class="sn-tree">' in h and "<div>" in h.split('<div class="sn-tree">')[1][:4000]) or "<tr>" in h
obs = [st for st in states if st.name == "The Obsidian window"]
print()
print("OBSIDIAN STATES after rename:", len(obs))
for st in obs:
    d = st.main_doc()
    trees = [q for q in st.parts if q["fam"] == "tree"]
    print("=" * 100)
    print("times", st.times, "title", repr(st.title), "fragment", st.fragment(), "has_structure", _has_structure(st))
    print("parts", [(q["fam"], q["slot"]) for q in st.parts])
    print("doc lines:", len(d.lines) if d else None)
    if d:
        for t, _ in d.lines:
            print("   D|", repr(flat(t)[:110]))
    for q in trees:
        m = q["model"]
        rows = getattr(m, "lines", None) or getattr(m, "rows", None) or []
        print("tree slot", q["slot"], "lines:", len(rows))
        for r in rows[:8]:
            print("   T|", repr((flat(r[0]) if isinstance(r, tuple) else str(r))[:100]))
        if len(rows) > 8: print("   T| ... (%d more)" % (len(rows) - 8))
    print("rects:", dict(list(st.rects.items())[:12]))
    print("measured:", sorted(getattr(st, "measured", {}).keys()))
print()
print("FOLD TEST (words of 4+ letters, 90% containment):")
words = {id(o): _card_words(o) for o in obs}
for o in obs:
    mine = words[id(o)]
    others = set().union(*[words[id(x)] for x in obs if x is not o]) or set()
    inter = mine & others
    print("state", o.times[0], "structure=%s nwords=%d contained=%d (%.0f%%) -> %s" % (
        _has_structure(o), len(mine), len(inter), 100.0 * len(inter) / max(1, len(mine)),
        "FOLD" if (not _has_structure(o) and mine and len(inter) >= 0.9 * len(mine)) else "KEEP"))
    if len(mine) <= 40:
        print("   words:", sorted(mine))
        print("   missing from others:", sorted(mine - others))
# shared moments
import itertools
for a, b in itertools.combinations(obs, 2):
    sh = set(a.times) & set(b.times)
    print("shared moments", a.times[0], "x", b.times[0], "->", sorted(sh))
