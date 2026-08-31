import json
rows = json.load(open("_probe/confirmed.json"))
BAR = 12
print("%-26s %5s   %-22s %-22s" % ("video", "n", "screens now / at 12", "cameras now / at 12"))
for d in sorted(set(r["vid"] for r in rows)):
    v = [r for r in rows if r["vid"] == d]
    scr = [r for r in v if r["want"] == "screen"]
    cam = [r for r in v if r["want"] == "camera"]
    now_s = sum(1 for r in scr if r["boxes"] >= 5)
    bar_s = sum(1 for r in scr if r["boxes"] >= BAR)
    now_c = sum(1 for r in cam if r["boxes"] >= 5)
    bar_c = sum(1 for r in cam if r["boxes"] >= BAR)
    print("%-26s %5d   kept %2d of %2d -> %2d      wrongly kept %2d -> %2d"
          % (d[:26], len(v), now_s, len(scr), bar_s, now_c, bar_c))
