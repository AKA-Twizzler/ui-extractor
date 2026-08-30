# diagC-1: raw pane lines of the cut-off Finder (x<100) and the memory Finder,
# per moment, then the harmonised memory table rows and the cut-off table rows.
import sys, os, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw3, draw2, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
WANT = {"00:01:20","00:01:30","00:01:40","00:01:50","00:02:20","00:02:50","00:03:00","00:03:30","00:03:40","00:03:50"}
for m in moments:
    if m["ts"] not in WANT: continue
    print("=" * 100)
    print("MOMENT", m["ts"], "size", m.get("size"))
    for w in m.get("windows") or []:
        print("  WIN wi=%s rect=%s top=%r" % (w.get("wi"), w.get("rect"), w.get("top")))
    for g in draw2.window_groups(m):
        r = g["rect"]
        if r[0] > 100 and g.get("title") != "memory":
            continue
        print("  GROUP name=%r title=%r rect=%s wi=%s" % (g["name"], g.get("title"), r, g.get("wi")))
        for p in g["panes"]:
            print("    PANE kind=%r box=%s" % (p["kind"], p["box"]))
            for ln in p.get("lines") or []:
                print("       |", ln)
            d = p.get("data") or {}
            if d.get("readings"):
                for rd in d["readings"]:
                    print("       rd:", json.dumps({k: rd.get(k) for k in ("text","box","confirmed")}, ensure_ascii=False))
            print("    bar_crumbs:", draw3.bar_crumbs(p))
        print("    bar_across:", draw3.bar_across(g, m))
print("=" * 100)
states = draw3.build_states(moments)
def dump(st, label):
    t = st.main_table()
    print("--- %s: name=%r title=%r times=%s" % (label, st.name, st.title, st.times))
    if not t: print("   no table"); return
    print("   header", t.header)
    print("   path", t.path)
    for ts, rd in t.readings: print("   reading %s: %s" % (ts, rd))
    for i, r in enumerate(t.rows):
        print("   row %2d %s italic=%s" % (i, r["cells"], r["italic"]))
for st in states:
    if st.name == "The Finder window" and (st.title == "memory" or not st.title):
        dump(st, "BEFORE harmonise")
draw3.harmonise(states)
for st in states:
    if st.name == "The Finder window" and (st.title == "memory" or not st.title):
        dump(st, "AFTER harmonise")
