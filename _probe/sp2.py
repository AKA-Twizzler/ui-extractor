import sys, time; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import machine, tree_reader, console_reader, columns, chat_reader, note_reader, verify_names, style_reader
from rapidocr_onnxruntime import RapidOCR
engine = RapidOCR()
base = "/mnt/g/Images/Live Replay - July 6, 2026; AI marketing, Jarvis builds, and AI automation/Images/"
for name in ("01-00-00_pane1.png", "01-00-00_pane0.png"):
    p = machine.here(base + name)
    import cv2; img = cv2.imread(p); print(name, img.shape)
    t = time.perf_counter(); res, _ = engine(p); print("  rapidocr", round(time.perf_counter()-t, 2), len(res or []))
    t = time.perf_counter(); console_reader.read_console(p); print("  console", round(time.perf_counter()-t, 2))
    t = time.perf_counter(); columns.read_list(p); print("  columns", round(time.perf_counter()-t, 2))
    t = time.perf_counter(); chat_reader.read_chat(p, engine=engine); print("  chat", round(time.perf_counter()-t, 2))
    t = time.perf_counter(); note_reader.read_note(p); print("  note", round(time.perf_counter()-t, 2))
    texts = [x for _, x, _ in (res or [])]
    t = time.perf_counter(); verify_names.confirm_readings(p, texts); print("  confirm", round(time.perf_counter()-t, 2))
    t = time.perf_counter(); style_reader.measure(p, "text, not a tree", {"readings": [{"text": x, "box": style_reader._box(b)} for b, x, _ in (res or [])]}, res); print("  style", round(time.perf_counter()-t, 2))
