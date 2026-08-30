import sys, time; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import concurrent.futures, machine, pipeline
from rapidocr_onnxruntime import RapidOCR
engine = RapidOCR()
base = "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/"
panes = [machine.here(base + n) for n in ("00-03-00_pane4.png", "00-04-10_pane0.png", "00-04-10_pane2.png", "00-03-00_pane2.png", "00-03-00_pane0.png")]
def one(p):
    t = time.perf_counter()
    rec = pipeline.say_pane(p, 0, engine, (), None, in_ui=True)
    return rec["kind"], len(rec["lines"]), round(time.perf_counter() - t, 1)
t = time.perf_counter()
seq = [one(p) for p in panes]
print("sequential", round(time.perf_counter() - t, 1), seq)
t = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    par = list(pool.map(one, panes))
print("parallel  ", round(time.perf_counter() - t, 1), par)
print("same kinds and line counts:", [x[:2] for x in seq] == [x[:2] for x in par])
