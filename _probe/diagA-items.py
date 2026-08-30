# diagA: what draw2.items_of hands the _doc_wide measure for the Obsidian doc panes (read only)
import sys, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); os.chdir(r"G:\AI\Ethereal\ui-extractor")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import draw as old, draw2
header, moments, footer = old.load(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
for m in moments:
    if m["ts"] not in ("00:00:00", "00:04:40"):
        continue
    for q in m["panes"]:
        if q.get("kind") != "an open document":
            continue
        its = draw2.items_of(q)
        print("##", m["ts"], q["box"], "items:", len(its))
        for it in its:
            b = it["box"]
            print("   %-6s w=%5.0f box=[%.0f,%.0f,%.0f,%.0f] %r" % (it.get("role"), b[2]-b[0], b[0], b[1], b[2], b[3], it["text"][:50]))
