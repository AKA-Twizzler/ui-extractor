import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
for st in states:
    if st.times == ["00:03:06"]:
        t = st.main_table()
        print("title", repr(st.title), "from_path", getattr(st, "title_from_path", None), "sure", getattr(st, "title_sure", None))
        print("path", t.path)
        print("readings", [(k, v) for k, v in (getattr(t, "readings", {}) or {}).items()][:6] if isinstance(getattr(t, "readings", None), dict) else getattr(t, "readings", None))
        print("topwords", [w[0] for w in st.topwords][:10])
        print("names", t.names())
        for r in t.rows[:20]:
            print("   ", r["cells"])
draw3.harmonise(states)
for st in states:
    if st.times == ["00:03:06"]:
        t = st.main_table()
        print("after harmonise: title", repr(st.title), "path", t.path)
        for r in t.rows[:20]:
            print("   ", r["cells"])
print("VOTES")
states = draw3.build_states(moments)
for st in states:
    if st.times == ["00:03:06"]:
        t = st.main_table()
        for r in t.rows:
            print("   ", r["cells"][0][:40], "|", r["cells"][1:], "| votes", r.get("_names"))
