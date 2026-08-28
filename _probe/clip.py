import os, sys, json, copy
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw2, shapes
REC = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-02-50.png"
W, H = shapes._frame_size(P)
win = [r for r in shapes.windows(P) if r[0] < 0.02 * W and (r[2]-r[0])*(r[3]-r[1]) >= 0.09*W*H]
print("measured left window:", [round(v) for v in win[0]] if win else None)
for line in open(REC, encoding="utf-8"):
    r = json.loads(line)
    if r.get("secs") != 170:
        continue
    for p in (r.get("panes") or []):
        b = p.get("box") or []
        if not (b and b[0] < 700 and (b[2]-b[0]) < 900):
            continue
        print("raw pane box", [round(v) for v in b], "-> cut_list", bool(draw2.cut_list(p, r.get("size"))))
        if win:
            w = win[0]
            q = copy.deepcopy(p)
            q["box"] = [max(b[0], w[0]), max(b[1], w[1]), min(b[2], w[2]), min(b[3], w[3])]
            for it in draw2.items_of(q):
                pass
            kept = [it for it in (q.get("data") or {}).get("items", []) or []]
            cut = draw2.cut_list(q, r.get("size"))
            print("clipped to the window", [round(v) for v in q["box"]], "-> cut_list", bool(cut),
                  "(%d rows)" % (len(cut[3]) if cut else 0))
