import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, numpy as np, machine, style_reader as sr, tree_reader, note_reader
base = "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/"
for name in ("00-03-00.png", "00-04-10.png", "00-01-20.png"):
    g = cv2.imread(machine.here(base + name), cv2.IMREAD_GRAYSCALE)
    print("pointer", name, sr.pointer(g))
p = machine.here(base + "00-03-00_pane4.png"); img = cv2.imread(p)
rows = tree_reader.ocr_rows(p)
ic = sr.icons_before(img, rows)
print("icons", [(r.get("text","")[:12], i["hue"]) for r, i in zip(rows, ic) if i])
print("pictures", [(x["box"], x["cells"]) for x in sr.pictures(img, [[r["x0"], r["y0"], r["x1"], r["y1"]] for r in rows])][:6])
p2 = machine.here(base + "00-04-10_pane2.png")
note = note_reader.read_note(p2)
big = cv2.imread(p2.replace(".png", "_3x.png"), cv2.IMREAD_GRAYSCALE)
mask = sr.ink_mask(big)
n_ul = 0
for r in note["rows"]:
    cell = mask[r["y0"]:r["y1"], r["x0"]:r["x1"]]
    ul = sr.underline(cell, r["xh"])
    if ul: n_ul += 1; print("  underline?", ul, r["text"][:40])
    # per-word slant
    for w in r.get("words") or []:
        t, x0, x1 = w[0], w[1], w[2]
        if len(t) >= 4:
            wc = mask[r["y0"]:r["y1"], x0:x1]
            sl = sr.slant(wc)
            if abs(sl) >= 7: print("  slanted word", t, sl)
print("underlines", n_ul)
