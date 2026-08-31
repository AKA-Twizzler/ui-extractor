import sys, time, collections
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst
N = collections.Counter(); T = collections.Counter()
def wrap(name):
    f = getattr(pixfirst, name)
    def g(*a, **k):
        t = time.perf_counter()
        try: return f(*a, **k)
        finally:
            N[name] += 1; T[name] += time.perf_counter() - t
    setattr(pixfirst, name, g)
for n in ("_rapid_text", "ocr", "tess_word", "word_crops", "read_cell", "batch_read", "_cell_crop", "batch_tess", "_tess_tsv"):
    wrap(n)
pixfirst.engine()
t = time.perf_counter()
out = pixfirst.read_frame(sys.argv[1], title_hint="memory")
tot = time.perf_counter() - t
rows = sum(len(w.get("rows") or []) for w in (out.get("windows") or [])) if isinstance(out, dict) else 0
print("\n==== one pane, %.1f s total, %d rows" % (tot, rows))
print("%-14s %7s %9s %8s" % ("call", "times", "seconds", "each"))
for n, c in N.most_common():
    print("%-14s %7d %9.1f %8.3f" % (n, c, T[n], T[n]/c))
inner = T["_rapid_text"] + T["ocr"] + T["tess_word"]
print("\nengine calls total %.1f s of %.1f s  (%.0f%%)" % (inner, tot, 100*inner/tot))
print("per-word calls (ocr): %d of %d engine calls = %.0f%%" % (
      N["ocr"], N["ocr"]+N["_rapid_text"]+N["tess_word"],
      100*N["ocr"]/max(1, N["ocr"]+N["_rapid_text"]+N["tess_word"])))
