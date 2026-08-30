import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
def mem(states):
    for st in states:
        if st.times and st.times[0] == "00:01:20" and st.name == "The Finder window":
            return st
    return None
def claude(states):
    for st in states:
        if st.times == ["00:00:50"] and st.name == "The Finder window":
            return st
m = mem(states)
print("start        ", m.main_table().path)
for i in range(1, 6):
    draw3.harmonise(states)
    print("harmonise x%d " % i, m.main_table().path)

print()
print("=== now emulate polish() over slices, in note()'s order ===")
states = draw3.build_states(moments)
m = mem(states)
print("fresh        ", m.main_table().path)
order = [mm["ts"] for mm in moments]
for st in list(states):
    if st.name != "The Finder window":
        continue
    t0, t1 = st.times[0], st.times[-1]
    sl = draw3.state_slice(st, t0, t1)
    if sl is None:
        continue
    draw3.polish(sl, states)
    print("after polish(%s..%s of %-28r) memory path = %s"
          % (t0, t1, st.title, m.main_table().path))
