import sys, time; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import machine, note_reader, style_reader, verify_names, tree_reader, console_reader, columns, chat_reader
from rapidocr_onnxruntime import RapidOCR
engine = RapidOCR()
p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-04-10_pane2.png")
t = time.perf_counter(); res, _ = engine(p); print("rapidocr", round(time.perf_counter()-t, 1), len(res))
t = time.perf_counter(); tree_reader.read_tree(p); print("tree", round(time.perf_counter()-t, 1))
t = time.perf_counter(); console_reader.read_console(p); print("console", round(time.perf_counter()-t, 1))
t = time.perf_counter(); columns.read_list(p, readings=len(res)); print("columns", round(time.perf_counter()-t, 1))
t = time.perf_counter(); chat_reader.read_chat(p, engine=engine); print("chat", round(time.perf_counter()-t, 1))
t = time.perf_counter(); note = note_reader.read_note(p); print("note", round(time.perf_counter()-t, 1))
t = time.perf_counter(); style_reader.measure(p, "an open document", note, res); print("style", round(time.perf_counter()-t, 1))
t = time.perf_counter(); verify_names.confirm_readings(p, [x for _, x, _ in res]); print("confirm", round(time.perf_counter()-t, 1))
