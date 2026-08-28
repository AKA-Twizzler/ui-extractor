import os, sys, importlib
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-00-10.png"
for which in ("_probe/shapes.clean.py", "shapes.py"):
    src = open(os.path.join(r"/home/trism/.claude/jobs/014c964f/tmp/replay", which.replace("/", "\\")), encoding="utf-8").read()
    mod = {"__name__": "shapes_probe"}
    exec(compile(src, which, "exec"), mod)
    W, H = mod["_frame_size"](P)
    ws = mod["windows"](P)
    big = [r for r in ws if (r[2]-r[0])*(r[3]-r[1]) >= 0.09*W*H]
    print("%-24s windows=%d window-sized=%d" % (which, len(ws), len(big)))
    for r in big:
        print("      x %.3f-%.3f y %.3f-%.3f  %.1f%%" % (r[0]/W, r[2]/W, r[1]/H, r[3]/H, 100*(r[2]-r[0])*(r[3]-r[1])/(W*H)))
