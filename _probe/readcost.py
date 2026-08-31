"""Where a pane's READ time goes, reader by reader and call by call.

The drawing's cost turned out to be the NUMBER of engine calls rather than
the pixels in them. This asks the same question of the read, which is now
the bigger half of a run: which reader in the cascade spends the time, and
how many times does each of them wake an engine or spawn a process.
"""
import sys, time, collections, glob, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe")
import pipeline, verify_names

N = collections.Counter(); T = collections.Counter()
def wrap(mod, name, label=None):
    f = getattr(mod, name, None)
    if f is None: return
    label = label or name
    def g(*a, **k):
        t = time.perf_counter()
        try: return f(*a, **k)
        finally: N[label] += 1; T[label] += time.perf_counter() - t
    setattr(mod, name, g)

wrap(verify_names, "_tess_line", "tesseract process")
wrap(verify_names, "read_row", "verify: one row")
wrap(verify_names, "verify", "verify: whole tree")
for m, n in (("columns", "read_list"), ("tree_reader", "read_tree"),
             ("style_reader", "measure"), ("overlay", "read_overlays")):
    try: wrap(__import__(m), n, "%s.%s" % (m, n))
    except Exception: pass

panes = sorted(glob.glob(r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\*_pane*.png"))
panes = [p for p in panes if "-overlay" not in p][:int(sys.argv[1]) if len(sys.argv) > 1 else 6]
print("%d panes" % len(panes))
eng = pipeline.engine if hasattr(pipeline, "engine") else None
t0 = time.perf_counter()
for p in panes:
    t = time.perf_counter()
    try:
        pipeline.say_pane(p, 0, eng, [], False, in_ui=True)
    except Exception as e:
        print("   %s -> %s: %s" % (os.path.basename(p)[:26], type(e).__name__, str(e)[:60]))
    print("   %-30s %5.1f s" % (os.path.basename(p)[:30], time.perf_counter()-t))
print("\ntotal %.1f s" % (time.perf_counter()-t0))
print("%-24s %7s %9s %8s" % ("reader / call", "times", "seconds", "each"))
for n, c in T.most_common():
    print("%-24s %7d %9.1f %8.3f" % (n, N[n], T[n], T[n]/max(1, N[n])))
