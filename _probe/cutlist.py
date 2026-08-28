import os, sys, json
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw2
REC = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
for line in open(REC, encoding="utf-8"):
    r = json.loads(line)
    if r.get("secs") not in (110, 170):
        continue
    size = r.get("size")
    for p in (r.get("panes") or []):
        b = p.get("box") or []
        if b and b[0] < 700 and (b[2] - b[0]) < 900:
            try:
                cut = draw2.cut_list(p, size)
            except Exception as e:
                cut = "ERROR %s" % e
            n = len(cut[3]) if cut and not isinstance(cut, str) else 0
            print("%s box=%s -> cut_list %s (%d rows)" % (r["ts"], [round(v) for v in b],
                                                          bool(cut) if not isinstance(cut, str) else cut, n))
