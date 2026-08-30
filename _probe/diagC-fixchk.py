import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
TBL = mem.main_table()
spans = draw3.screens(states, moments)
out = []
def liner(frame, event, arg):
    if event == "line" and frame.f_code.co_name == "harmonise" and frame.f_lineno == 3115:
        L = frame.f_locals
        if L.get("table") is TBL and L.get("c") == "projects" and L.get("b") == "projerts":
            out.append(dict(crumb_flats_has_projects="projects" in L["crumb_flats"],
                            title_flats_has_projects="projects" in L["title_flats"],
                            near=L.get("near")))
            # would the proposed guard block it?
    if event == "line" and frame.f_code.co_name == "harmonise" and frame.f_lineno == 3073:
        L = frame.f_locals
        if L.get("table") is TBL and "-Users-jaredrh" in (L.get("path") or []):
            longer = [w for p_ in L["table"].paths for w in p_
                      if draw3.crumb_same("-Users-jaredrh", w) and len(draw3.flat(w)) > len("usersjaredrh")]
            out.append(dict(split_input=list(L["path"]), longer_in_own_readings=longer))
    return liner
sys.settrace(lambda fr, ev, a: liner if fr.f_code.co_filename.endswith("draw3.py") else None)
for s in spans:
    for st in s["states"]:
        sl = draw3.state_slice(st, s["t0"], s["t1"])
        if sl is None or sl is st: continue
        draw3.polish(sl, states)
sys.settrace(None)
for o in out[:6]: print(o)
print("final:", TBL.path)
