import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, machine, style_reader as sr, tree_reader, note_reader, columns
from rapidocr_onnxruntime import RapidOCR
engine = RapidOCR()
base = "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/"
for name, kind in (("00-03-00_pane4.png", "a list of columns"), ("00-04-10_pane0.png", "a file tree"), ("00-04-10_pane2.png", "an open document"), ("00-03-00_pane2.png", "text, not a tree")):
    p = machine.here(base + name)
    res, _ = engine(p)
    if kind == "a list of columns":
        data = columns.read_list(p)
        # row boxes are not in the reader yet; borrow tesseract rows by y from the blocks' span
        for b in data["blocks"]:
            n = len(b["rows"]); y0, y1 = b["y0"], b["y1"]
            step = (y1 - y0) / max(1, n + 1)
            b["row_boxes"] = [[b["bands"][0][0], int(y0 + step * (i + 1)), b["bands"][-1][1], int(y0 + step * (i + 2))] for i in range(n)]
        data["scale"] = 3
    elif kind == "a file tree":
        data = tree_reader.read_tree(p)
    elif kind == "an open document":
        data = note_reader.read_note(p)
    else:
        data = {"readings": [{"text": t, "box": sr._box(b)} for b, t, _ in res]}
    print(name, "->", sr.measure(p, kind, data, res))
    if kind == "a file tree":
        print("   rows with marks:", [(r["name"][:14], r.get("band"), r.get("icon")) for r in data["rows"] if r.get("band") or r.get("icon")][:8])
    if kind == "a list of columns":
        print("   row_style:", data["blocks"][0].get("row_style"))
    if kind == "an open document":
        print("   italics:", [(r["text"][:30], r.get("italic")) for r in data["rows"] if r.get("italic")])
        print("   families:", [r.get("family") for r in data["rows"]][:12])
