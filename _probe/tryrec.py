import sys, glob, os, cv2
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import note_reader
d = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
cands = []
for f in glob.glob(os.path.join(d, "00-00-00_pane*.png")):
    if "_3x" in f or "_tess" in f:
        continue
    im = cv2.imread(f)
    if im is not None and im.shape[0] <= 70 and im.shape[1] > 500:
        cands.append((f, im.shape))
print("strip panes:", [(os.path.basename(f), s) for f, s in cands][:6])
for f, _s in cands[:2]:
    res = note_reader.read_note(f)
    for r in res.get("rows", [])[:4]:
        print(os.path.basename(f), "|primary:", repr(r.get("text_primary"))[:70],
              "|second:", repr(r.get("text_second"))[:70],
              "|kept:", repr(r.get("text"))[:70], "|status:", r.get("read_status"))
