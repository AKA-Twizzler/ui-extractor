import sys, time, os
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pipeline
from rapidocr_onnxruntime import RapidOCR
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
p = D + r"\00-01-30_pane3.png"
skip = {"terminal", "chat"} if sys.argv[1] == "gated" else set()
eng = RapidOCR()
t = time.perf_counter()
r = pipeline.say_pane(p, 0, eng, [], None, in_ui=True, box=(96, 272, 2376, 1612), skip=skip)
print("%-8s %6.1f s -> %s" % (sys.argv[1], time.perf_counter() - t, (r or {}).get("kind")))
