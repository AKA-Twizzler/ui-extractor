import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
def probe(label, run):
    states = draw3.build_states(moments)
    mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
    TBL = mem.main_table(); hits = []
    def liner(frame, event, arg):
        if event == "line" and frame.f_code.co_name == "harmonise" and frame.f_lineno == 3079:
            L = frame.f_locals
            if L.get("table") is TBL and L.get("f") == "projects":
                hits.append(dict(f=L["f"], b=L.get("b"),
                                 in_strong="projects" in L["strong_flats"],
                                 in_row="projects" in L["row_flats"]))
        return liner
    sys.settrace(lambda fr, ev, a: liner if fr.f_code.co_filename.endswith("draw3.py") else None)
    run(states, mem); sys.settrace(None)
    print(label, hits[:3], "| path:", TBL.main_table().path if hasattr(TBL,'main_table') else TBL.path)
probe("base   ", lambda s, m: draw3.harmonise(s))
probe("polish ", lambda s, m: draw3.polish(draw3.state_slice(m, "00:01:20", "00:01:40"), s))
