import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3, draw as old
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
# raw bars per moment, before any mending
import draw2
for m in moments:
    for g in draw2.window_groups(m):
        bar = []
        for p in g.get("panes") or []:
            c = draw3.bar_crumbs(p)
            if len(c) > len(bar): bar = c
        across = draw3.bar_across(g, m)
        if bar or across:
            print("RAW %s %-22s bar=%s across=%s" % (m["ts"], g["name"][:22], bar, across))
states = draw3.build_states(moments)
for st in states:
    t = st.main_table()
    if t and (t.path or t.readings):
        print("STATE %s %r path=%s" % (st.times[0], st.title, t.path))
        for ts, r in t.readings: print("      reading %s: %s" % (ts, r))
