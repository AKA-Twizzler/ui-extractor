"""Stack many cell crops into one tall image and read them in ONE engine call."""
import sys, time, json, numpy as np
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst, cv2
truth = json.load(open(r"G:\AI\Ethereal\ui-extractor\_probe\pixfirst-test\truth.json"))
pane = truth["panes"][1]
P = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png" % pane["frame"]
rgb = cv2.imread(P)[:, :, ::-1].copy()
rec = pixfirst.read_frame(P, None, "", wb=pane["wb"], list_box=True)
up = rec["up"]; lefts = [c[0]*up for c in rec["columns"]]; right = pane["wb"][2]-20
spans = [(lefts[i], lefts[i+1] if i+1 < len(lefts) else right) for i in range(len(lefts))]
crops = []
for r in rec["rows"]:
    ya, yb = r["y"][0]*up, r["y"][1]*up
    for (x0, x1) in spans:
        crops.append(rgb[max(0, ya-6):yb+6, x0:x1])
print("%d cells from %d rows" % (len(crops), len(rec["rows"])))
pixfirst.engine()
# --- one call each, as the reader does today ---
t = time.perf_counter()
one = [pixfirst.ocr(c, 3.0) for c in crops]
t_each = time.perf_counter() - t
# --- all of them stacked, one call ---
GAP = 24
t = time.perf_counter()
W = max(c.shape[1] for c in crops) + 40
H = sum(c.shape[0] for c in crops) + GAP*(len(crops)+1)
bg = np.median(np.concatenate([c.reshape(-1,3) for c in crops]), axis=0).astype(rgb.dtype)
canvas = np.empty((H, W, 3), dtype=rgb.dtype); canvas[:, :] = bg
at = []; y = GAP
for c in crops:
    canvas[y:y+c.shape[0], 20:20+c.shape[1]] = c
    at.append((y, y+c.shape[0])); y += c.shape[0] + GAP
SC = float(sys.argv[1]) if len(sys.argv)>1 else 1.0
got = pixfirst.ocr(canvas, SC)
t_stack = time.perf_counter() - t
print("scale", SC)
print("canvas %dx%d, engine returned %d boxes for %d cells" % (W, H, len(got), len(crops)))
print("one call per cell : %6.1f s  (%d calls)" % (t_each, len(crops)))
print("one call for all  : %6.1f s  (1 call)" % t_stack)
print("stacked is %.1fx faster" % (t_each/max(t_stack, .001)))
# assign each box back to its cell by y-centre, and compare the text
back = [""]*len(crops)
for b in got:
    yc = (b[1]+b[3])/2
    for i,(a_,b_) in enumerate(at):
        if a_-GAP/2 <= yc <= b_+GAP/2: back[i] = (back[i]+" "+b[4]).strip(); break
same = sum(1 for i,c in enumerate(one)
           if "".join(w[4] for w in sorted(c, key=lambda w: w[0])).replace(" ","") == back[i].replace(" ",""))
print("cells whose stacked reading matches the one-at-a-time reading: %d of %d" % (same, len(crops)))
for i in range(min(10, len(crops))):
    a = "".join(w[4] for w in sorted(one[i], key=lambda w: w[0]))
    if a.replace(" ","") != back[i].replace(" ",""):
        print("   differs: alone %r  stacked %r" % (a, back[i]))
