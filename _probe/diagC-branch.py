import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
TBL = mem.main_table()
spans = draw3.screens(states, moments)
WATCH = sys.argv[1]
last = [list(TBL.path)]
prev = [None]
snap = [None]
def liner(frame, event, arg):
    if event != "line":
        return liner
    ln, fn = frame.f_lineno, frame.f_code.co_name
    if fn == "harmonise" and ln in (3071, 3084, 3113, 3115):
        L = frame.f_locals
        snap[0] = {k: L.get(k) for k in ("c", "b", "f", "near", "starts", "i") if k in L}
        snap[0]["title_flats_has_projects"] = "projects" in (L.get("title_flats") or set())
        snap[0]["crumb_flats_has_projects"] = "projects" in (L.get("crumb_flats") or set())
    if fn == "harmonise" and ln == 3066:      # path[:] = split_
        L = frame.f_locals
        if any("jarvis" in str(x) or "Users" == str(x) for x in (L.get("split_") or [])):
            pass
    now = TBL.path
    if now != last[0]:
        print("  CHANGE at %s:%s -> %s" % (fn, prev[0], now))
        print("        locals:", snap[0])
        last[0] = list(now)
    prev[0] = ln
    return liner
def tracer(frame, event, arg):
    return liner if frame.f_code.co_filename.endswith("draw3.py") else None
for s in spans:
    for st in s["states"]:
        sl = draw3.state_slice(st, s["t0"], s["t1"])
        if sl is None or sl is st: continue
        on = (s["t0"] == WATCH)
        if on:
            print("### span %s, slice of %r" % (s["t0"], st.title)); sys.settrace(tracer)
        draw3.polish(sl, states)
        if on: sys.settrace(None)
print("final:", TBL.path)
