import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
TBL = mem.main_table()
spans = draw3.screens(states, moments)
WATCH = os.environ.get("WATCH_SPAN", "00:01:20")

last = [list(TBL.path)]
prev = [None]
def tracer(frame, event, arg):
    if frame.f_code.co_filename.endswith("draw3.py"):
        return liner
    return None
def liner(frame, event, arg):
    if event == "line":
        now = TBL.path
        if now != last[0]:
            print("   CHANGE -> %s\n      last executed line: %s:%s in %s"
                  % (now, "draw3.py", prev[0][1], prev[0][0]))
            print("      source:", open("draw3.py",encoding="utf-8").read().splitlines()[prev[0][1]-1].strip())
            last[0] = list(now)
        prev[0] = (frame.f_code.co_name, frame.f_lineno)
    return liner

for s in spans:
    for st in s["states"]:
        sl = draw3.state_slice(st, s["t0"], s["t1"])
        if sl is None or sl is st:
            continue
        on = (s["t0"] == WATCH)
        if on:
            print("### tracing polish over span %s (slice of %r)" % (s["t0"], st.title))
            sys.settrace(tracer)
        draw3.polish(sl, states)
        if on:
            sys.settrace(None)
print("final :", TBL.path)
