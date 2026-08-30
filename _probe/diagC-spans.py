import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
print("fresh :", mem.main_table().path)
spans = draw3.screens(states, moments)
print("spans :", [(s["t0"], s["t1"], len(s["states"])) for s in spans])
last = list(mem.main_table().path)
for s in spans:
    for st in s["states"]:
        sl = draw3.state_slice(st, s["t0"], s["t1"])
        if sl is None or sl is st:
            continue
        draw3.polish(sl, states)
        now = mem.main_table().path
        if now != last:
            print("  CHANGED during span %s-%s, slice of %-30r -> %s"
                  % (s["t0"], s["t1"], st.title, now))
            last = list(now)
print("final :", mem.main_table().path)
