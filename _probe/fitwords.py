import json, io, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import draw3, draw2
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
recs = [json.loads(l) for l in io.open(D, encoding="utf-8") if l.strip()]
moments = [r for r in recs if r.get("kind") == "moment"]
def word_boxes(m):
    seen = {}
    for p in m.get("panes") or []:
        for it in draw2.items_of(p):
            key = draw3.fold(draw3.flat(it["text"]))
            if len(key) >= 5:
                seen.setdefault(key, []).append(it["box"])
    return {k: v[0] for k, v in seen.items() if len(v) == 1}
words = {m["ts"]: word_boxes(m) for m in moments}
base = max(words, key=lambda t: len(words[t]))
print("base moment:", base, len(words[base]), "words")
for ts in sys.argv[1:]:
    m4 = words[ts]
    ex = [(k, words[base][k], m4[k]) for k in m4 if k in words[base]]
    print("==", ts, "words:", len(m4), "exact matches with base:", len(ex))
    for k, p, q in ex[:45]:
        kw = (q[2]-q[0])/max(1,(p[2]-p[0])); kh = (q[3]-q[1])/max(1,(p[3]-p[1]))
        print("  %-28s base x%5d y%5d w%4d h%3d | frame x%5d y%5d w%4d h%3d | kw %.2f kh %.2f" % (k[:28], p[0], p[1], p[2]-p[0], p[3]-p[1], q[0], q[1], q[2]-q[0], q[3]-q[1], kw, kh))
