import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
for st in states:
    t = st.main_table()
    print("%-22s title=%-28r times=%s..%s (%d) rows=%s path=%s measured=%s frag=%s parts=%s" % (
        st.name, st.title, st.times[0], st.times[-1], len(st.times),
        len(t.rows) if t else None, (t.path if t else None), sorted(st.measured.keys())[:3], st.fragment(),
        [(q["fam"], q["slot"]) for q in st.parts]))
