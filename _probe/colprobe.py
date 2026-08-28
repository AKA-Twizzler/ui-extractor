import json, io, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import draw2
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl"
HEAD = ("Name", "Date Modified", "Size", "Kind")
for l in io.open(D, encoding="utf-8"):
    r = json.loads(l)
    for p in r.get("panes") or []:
        if p.get("kind") != "a list of columns" or len(p.get("box") or []) != 4: continue
        b = p["box"]; W = float(b[2]-b[0])
        xs = {}; dims = {}
        for it in draw2.items_of(p):
            t = re.sub(r"\s+", " ", it["text"].strip())
            for h in HEAD:
                if h in xs: continue
                if t == h or (t.split()[0] == h.split()[0] and (len(h.split()) == 1 or t.startswith(h[:6]))):
                    xs[h] = float(it["box"][0]); dims[h] = (it["box"][2]-it["box"][0], it["box"][3]-it["box"][1])
        if len(xs) < 4: continue
        bounds = [b[0], xs["Date Modified"], xs["Size"], xs["Kind"], b[2]]
        sh = [(bounds[k+1]-bounds[k])/W for k in range(4)]
        loose = ["%s w%d/h%d" % (h[:4], dims[h][0], dims[h][1]) for h in HEAD if dims[h][0] > 3.0*dims[h][1]*len(h)/4.0]
        print("%s pane [%5d..%5d] W=%5d  shares %s  %s" % (r["ts"], b[0], b[2], W, " ".join("%4.1f" % (100*s) for s in sh), " LOOSE: " + ", ".join(loose) if loose else ""))
