"""Does one crop per ROW cost less than one crop per CELL, and does it read the same?"""
import sys, time, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst, cv2
truth = json.load(open(r"G:\AI\Ethereal\ui-extractor\_probe\pixfirst-test\truth.json"))
pane = truth["panes"][1]
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png" % pane["frame"]
rgb = cv2.imread(P)[:, :, ::-1].copy()
rec = pixfirst.read_frame(P, None, "", wb=pane["wb"], list_box=True)
up = rec["up"]; pitch = rec["pitch"] * up
lefts = [c[0] * up for c in rec["columns"]]
right = pane["wb"][2] - 20
spans = [(lefts[i], (lefts[i+1] if i+1 < len(lefts) else right)) for i in range(len(lefts))]
print("column spans", spans, " pitch", pitch, " rows", len(rec["rows"]))
pixfirst.engine()
tcell = trow = 0.0; ncell = nrow = 0
for r in rec["rows"][:6]:
    ya, yb = r["y"][0] * up, r["y"][1] * up
    t = time.perf_counter()
    for (x0, x1) in spans:
        pixfirst.ocr(rgb[max(0, ya-6):yb+6, x0:x1], 3.0); ncell += 1
    tcell += time.perf_counter() - t
    t = time.perf_counter()
    got = pixfirst.ocr(rgb[max(0, ya-6):yb+6, spans[0][0]:right], 3.0); nrow += 1
    trow += time.perf_counter() - t
    words = " / ".join(w[4] for w in sorted(got, key=lambda w: w[0]))
    print("  y=%4d  %d cell calls  |  the row in one call: %s" % (ya, len(spans), words[:95]))
print()
print("six rows, cell by cell : %5.1f s  (%d calls, %.3f each)" % (tcell, ncell, tcell/ncell))
print("six rows, row at a time: %5.1f s  (%d calls, %.3f each)" % (trow, nrow, trow/nrow))
print("row at a time is %.1fx %s" % (max(tcell, trow)/min(tcell, trow), "FASTER" if trow < tcell else "SLOWER"))
