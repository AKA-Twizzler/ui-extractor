import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
def probe(pool_label, run):
    states = draw3.build_states(moments)
    mem = next(st for st in states if st.name == "The Finder window" and st.times[0] == "00:01:20")
    TBL = mem.main_table()
    seen = {}
    def liner(frame, event, arg):
        if event != "line": return liner
        if frame.f_code.co_name == "harmonise" and frame.f_lineno == 3076 and frame.f_locals.get("table") is TBL:
            L = frame.f_locals
            if L.get("c") == "projects":
                seen.setdefault("hit", dict(
                    c=L["c"], f=L["f"], b=L.get("b"),
                    in_strong=L["f"] in L["strong_flats"], in_row=L["f"] in L["row_flats"],
                    strong_close=sorted({p for p in L["strong_names"] if str(p).startswith("pro")}),
                ))
        return liner
    def tracer(frame, event, arg):
        return liner if frame.f_code.co_filename.endswith("draw3.py") else None
    sys.settrace(tracer); run(states, mem); sys.settrace(None)
    print(pool_label, "->", seen.get("hit"), "| path:", TBL.path)

probe("plain harmonise(states)      ", lambda s, m: draw3.harmonise(s))
def with_slice(states, mem):
    sl = draw3.state_slice(mem, "00:01:20", "00:01:20")
    draw3.polish(sl, states)
probe("polish(memory slice, states) ", with_slice)
