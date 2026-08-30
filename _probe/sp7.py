import sys; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import json, verify_names
path = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records-at.jsonl"
for line in open(path, encoding="utf-8"):
    e = json.loads(line)
    if e["kind"] != "moment" or e["ts"] != "00:04:10": continue
    for p in e["panes"]:
        if p["kind"] != "an open document": continue
        for r in p["data"]["rows"]:
            if "worker" in (r.get("text") or "").lower():
                print("primary", repr(r.get("text_primary")), "\nsecond ", repr(r.get("text_second")), "\nfinal  ", repr(r["text"]), r.get("read_status"))
                print(verify_names.reconcile(r["text_primary"], r["text_second"]))
