import sys, os, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
print("### BEFORE HARMONISE")
for i, st in enumerate(states):
    t = st.main_table()
    if not t: continue
    print("STATE %02d %-24s title=%r times=%s" % (i, st.name[:24], st.title, st.times))
    print("     path   :", t.path)
    for ts, r in t.readings:
        print("     reading %s: %s" % (ts, r))
    print("     header :", t.header)
    for r in t.rows:
        print("       ROW", r["cells"])
print()
draw3.harmonise(states)
print("### AFTER HARMONISE")
for i, st in enumerate(states):
    t = st.main_table()
    if not t: continue
    print("STATE %02d %-24s title=%r times=%s" % (i, st.name[:24], st.title, st.times))
    print("     path   :", t.path)
