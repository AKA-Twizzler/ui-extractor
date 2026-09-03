import sys
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst
F = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png"
for fr, wb in (("00-00-00", [2153, 494, 3192, 1148]), ("00-00-30", [88, 272, 2372, 1680]), ("00-00-00", [773, 472, 1748, 1140])):
    rec = pixfirst.read_frame(F % fr, r"G:\AI\Ethereal\ui-extractor\_probe\pixfirst-test", "", wb=wb, list_box=True)
    print("==", fr, wb, "up", rec["up"], "header", rec["header"], "foot", rec["path_top"], "pitch", rec["pitch"], "cols", rec["columns"])
    for r in rec["rows"]:
        print("   ", "CUT " if r["cut"] else "    ", (r["icon"] or "").ljust(6), r["y"], "%.2f" % r["conf"], " | ".join(r["cells"])[:110])
