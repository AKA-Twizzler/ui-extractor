import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
TBL = mem.main_table()
spans = draw3.screens(states, moments)
last = [list(TBL.path)]
def liner(frame, event, arg):
    if event != "line": return liner
    ln, fn = frame.f_lineno, frame.f_code.co_name
    L = frame.f_locals
    if fn == "harmonise" and ln == 3066 and L.get("table") is TBL:
        print("   split_ block: in=%s\n                 out=%s" % (L.get("path"), L.get("split_")))
    if fn == "chain_paths" and ln == 2731 and len(L.get("base") or []) and "memory" in " ".join(map(str,L["base"])).lower():
        print("   chain_paths -> %s" % (L.get("base"),))
    if fn == "harmonise" and ln == 3134 and L.get("table") is TBL:
        print("   readings fed to chain_paths (late): %s" % (L.get("late"),))
    now = TBL.path
    if now != last[0]:
        print("   >>> TBL.path now %s   (after %s:%s)" % (now, fn, ln))
        last[0] = list(now)
    return liner
def tracer(frame, event, arg):
    return liner if frame.f_code.co_filename.endswith("draw3.py") else None
for s in spans:
    for st in s["states"]:
        sl = draw3.state_slice(st, s["t0"], s["t1"])
        if sl is None or sl is st: continue
        on = (s["t0"] == "00:02:20" and st.title == "vault-demo")
        if on:
            print("### span 00:02:20, slice of 'vault-demo'"); print("   TBL.path before:", TBL.path)
            print("   TBL.readings:", TBL.readings)
            sys.settrace(tracer)
        draw3.polish(sl, states)
        if on: sys.settrace(None); print("   TBL.path after :", TBL.path)
