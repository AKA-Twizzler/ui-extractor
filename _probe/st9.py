import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import cv2, numpy as np, machine, style_reader as sr, note_reader
base = "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/"
p2 = machine.here(base + "00-04-10_pane2.png")
note = note_reader.read_note(p2)
big = cv2.imread(p2.replace(".png", "_3x.png"), cv2.IMREAD_GRAYSCALE)
mask = sr.ink_mask(big)
for r in note["rows"]:
    if "doesn" in r["text"] or "Everyagent" in r["text"] or "This note" in r["text"]:
        print("ROW", r["text"][:60], "xh", r["xh"])
        for w in r.get("words") or []:
            t, x0, x1 = w[0], w[1], w[2]
            wc = mask[r["y0"]:r["y1"], x0:x1]
            print(f"   {t!r:20} slant {sr.slant(wc):5.1f}  w={x1-x0}")
        # save a crop of the row for viewing
        if "doesn" in r["text"]:
            cv2.imwrite(machine.here("/home/trism/.claude/jobs/014c964f/tmp/replay/_probe/st9_row.png"), big[r["y0"]-5:r["y1"]+5, r["x0"]:r["x0"]+1400])
