import sys, os, json
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
draw3.harmonise(states)
for st in states:
    t = st.main_table()
    if st.name == "The Finder window" and (not st.title or st.title == "memory"):
        print("FINDER", repr(st.title), st.times, "heads", t.heads if t else None, "path", t.path if t else None, "rows", len(t.rows) if t else None)
    if st.name == "The Obsidian window":
        print("OBS", repr(st.title), st.times[0], st.times[-1], len(st.times), "parts", [(q["fam"], q["slot"]) for q in st.parts][:8], "topwords", [w[0] for w in st.topwords][:6])
for m in moments:
    for w in m.get("windows") or []:
        if w.get("top") and "ault" in w["top"]:
            print("TOP", m["ts"], w["wi"], repr(w["top"]), w.get("top_from"))
