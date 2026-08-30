import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw2, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
print("STATES FROM build_states:", len(states))
for i, st in enumerate(states):
    t = st.main_table()
    docs = [q for q in st.parts if q["fam"] == "doc"]
    trees = [q for q in st.parts if q["fam"] == "tree"]
    def nlines(q):
        m = q.get("model")
        return len(getattr(m, "lines", None) or getattr(m, "rows", None) or [])
    print("%2d %-22s title=%-30r times=%s parts=%s doclines=%s treelines=%s rect=%s" % (
        i, st.name, st.title, st.times, [(q["fam"], q["slot"]) for q in st.parts],
        [nlines(q) for q in docs], [nlines(q) for q in trees], getattr(st, "rect", None)))
print()
print("WINDOW GROUPS per moment (draw2.window_groups):")
for m in moments:
    if m["ts"] not in ("00:00:00", "00:00:10", "00:00:50", "00:01:10", "00:04:00", "00:04:10"):
        continue
    W = (m.get("size") or [1920])[0]
    for g in draw2.window_groups(m):
        print("  ", m["ts"], "group name=%r key=%r rect=%s panes=%s" % (
            g.get("name"), draw2.group_key(g, W), g.get("rect"),
            [(p.get("kind"), p.get("box"), len(p.get("lines") or [])) for p in g["panes"]]))
