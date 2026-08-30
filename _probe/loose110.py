import sys, os, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
import draw2
recs=[json.loads(l) for l in open(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl",encoding="utf-8") if l.strip()]
m=next(r for r in recs if r.get("ts")=="00:01:10")
for p in m["panes"]:
    if p["pi"] in (2,6):
        items=draw2.items_of(p)
        print("pane",p["pi"],p["box"],len(items),"items")
        for it in items: print("   ",repr(it["text"]),[round(v) for v in it["box"]],it["ok"],it["role"])
        rows=draw2.reading_order(items, lambda it: it["box"])
        for r in rows: print("   row:",[it["text"][:20] for it in r], "heads:",[h for it in r for h in draw2.split_heads(it["text"])])
        print("   table_from_loose ->", draw2.table_from_loose(p))
