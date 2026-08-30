import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw as old, furnish
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
states = draw3.build_states(moments)
draw3.list_not_tree(states)
house = max((furnish.side_words_of(st) for st in states if st.name == "The Finder window"), key=len, default=[])
print("house", house)
for st in states:
    if st.title == "jaredrhodenizer":
        t = st.main_table()
        print("before: side=", t.side, "parts=", [(q["fam"], q["x0"], q["x1"]) for q in st.parts])
        print("sidebar_from_panes ->", draw3.sidebar_from_panes(st, house))
        print("after: side=", t.side, "share=", getattr(st, "side_share", None), "parts=", [(q["fam"], q["x0"], q["x1"]) for q in st.parts])
        draw3.tidy_side(t, house, st.title)
        print("tidy: side=", t.side)
        print("side_words_of:", furnish.side_words_of(st))
