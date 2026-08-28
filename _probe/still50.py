import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
at_idx = {m["ts"]: i for i, m in enumerate(moments)}
print("idx", {k: v for k, v in at_idx.items() if k >= "00:02:50"})
states = draw3.build_states(moments)
for st in states:
    if st.name == "The Finder window" and not st.title:
        print("untitled finder times", st.times, "measured", sorted(st.measured), "rects", {t: [round(v) for v in r] for t, r in st.rects.items()})
    if st.title == "vault-demo":
        print("vault-demo times", st.times, "measured", sorted(st.measured), "rects", {t: [round(v) for v in r] for t, r in st.rects.items()})
