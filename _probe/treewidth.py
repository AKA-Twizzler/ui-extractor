"""How wide was the file tree REALLY, against the window it sat in? The card
says 10fr; the frame is the only thing that can say whether that is right."""
import sys, os
sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay"); os.chdir(r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import draw3
LIVE = []
real = draw3.State.__init__
def init(self, group, ts):
    real(self, group, ts); LIVE.append(self)
draw3.State.__init__ = init
draw3.note(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\records.jsonl")
print("%-9s %-22s %-26s %-24s %6s %6s" % ("moments", "window", "tree pane x0..x1", "window rect", "pane%", "_tree_fr"))
for st in LIVE:
    if "bsidian" not in (st.name or ""):
        continue
    tp = next((q for q in getattr(st, "parts", []) if q.get("fam") == "tree" and q.get("x0") is not None), None)
    rect = getattr(st, "shape", None) or getattr(st, "rect", None)
    if not tp or not rect:
        continue
    w = rect[2] - rect[0]
    pct = 100.0 * (tp["x1"] - tp["x0"]) / max(1.0, w)
    print("%-9s %-22s %-26s %-24s %5.1f%% %6s"
          % (st.times[0] if st.times else "-", (st.title or "-")[:22],
             "%.0f..%.0f (%.0f wide)" % (tp["x0"], tp["x1"], tp["x1"] - tp["x0"]),
             "%.0f..%.0f (%.0f wide)" % (rect[0], rect[2], w),
             pct, getattr(st, "_tree_fr", "-")))
