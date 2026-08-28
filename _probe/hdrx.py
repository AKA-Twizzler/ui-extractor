import json, io, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import draw2
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
for l in io.open(D, encoding="utf-8"):
    r = json.loads(l)
    if r.get("ts") not in sys.argv[1:]: continue
    for p in r["panes"]:
        if p.get("kind") != "a list of columns": continue
        print("==", r["ts"], "pane", [round(x) for x in p["box"]])
        for it in draw2.items_of(p):
            t = it["text"].strip()
            if t in ("Name", "Date Modified", "Size", "Kind", "Date Added", "Tags") or t.startswith("Date"):
                b = it["box"]; print("   %-14s x %5d..%5d y %5d" % (t, b[0], b[2], b[1]))
        rows = [it for it in draw2.items_of(p) if it["box"][1] > p["box"][1] + 60][:6]
        for it in rows:
            b = it["box"]; print("   row item %-30s x %5d..%5d" % (it["text"][:30], b[0], b[2]))
