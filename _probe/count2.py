import sys, time, json, collections
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor\_probe"); sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pixfirst
N = collections.Counter(); T = collections.Counter()
def wrap(name, mod=pixfirst):
    f = getattr(mod, name)
    def g(*a, **k):
        t = time.perf_counter()
        try: return f(*a, **k)
        finally: N[name] += 1; T[name] += time.perf_counter() - t
    setattr(mod, name, g)
for n in ("ocr", "tess_word", "_tess_tsv", "batch_read", "batch_tess", "win_words", "list_words", "word_crops", "leading_dot", "icon_of"):
    wrap(n)
truth = json.load(open(r"G:\AI\Ethereal\ui-extractor\_probe\pixfirst-test\truth.json"))
pane = truth["panes"][int(sys.argv[1])]
F = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\%s.png" % pane["frame"]
t = time.perf_counter(); pixfirst.read_frame(F, None, "", wb=pane["wb"], list_box=True); tot = time.perf_counter()-t
print("pane %s  %.1f s" % (pane["frame"], tot))
for n, c in N.most_common():
    if T[n] > 0.05: print("   %-12s %5d %7.1f s  %6.3f each" % (n, c, T[n], T[n]/c))
print("   %-12s %5s %7.1f s" % ("ACCOUNTED", "", sum(T[n] for n in ("ocr","tess_word","_tess_tsv","win_words","list_words","word_crops","leading_dot","icon_of"))))
