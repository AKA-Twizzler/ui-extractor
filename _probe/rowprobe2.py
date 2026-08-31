import sys, json
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst, cv2
truth = json.load(open(r"G:\AI\Ethereal\ui-extractor\_probe\pixfirst-test\truth.json"))
pane = truth["panes"][1]
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png" % pane["frame"]
rgb = cv2.imread(P)[:, :, ::-1].copy()
rec = pixfirst.read_frame(P, None, "", wb=pane["wb"], list_box=True)
up = rec["up"]; lefts = [c[0]*up for c in rec["columns"]]; right = pane["wb"][2]-20
pixfirst.engine()
for r in rec["rows"][:4]:
    ya, yb = r["y"][0]*up, r["y"][1]*up
    got = pixfirst.ocr(rgb[max(0,ya-6):yb+6, lefts[0]:right], 3.0)
    print("y=%4d  %d boxes" % (ya, len(got)))
    for w in sorted(got, key=lambda w: w[0]):
        print("      x %6.0f..%-6.0f  %r" % (w[0], w[2] if len(w) > 2 else -1, w[4]))
    print("   column lefts (crop-relative):", [l - lefts[0] for l in lefts])
