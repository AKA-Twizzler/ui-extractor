"""Why the reader under-covers two known frames. Read-only."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import note_reader, tree_reader, verify_names, columns
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
def p(name): return os.path.join(D, name)

print("=== note body pane 00-04-10_pane2 ===")
res, _ = eng(p("00-04-10_pane2.png"))
print("recogniser boxes:", len(res or []))
for b, t, s in (res or [])[:60]:
    ys = [q[1] for q in b]; print(f"  y={int(min(ys)):5} h={int(max(ys)-min(ys)):3} {t[:90]}")
note = note_reader.read_note(p("00-04-10_pane2.png"))
print("read_note: rows", len(note.get("rows", [])), "backed", note.get("backed"), "body_lines", note_reader.body_lines(note["markdown"]), "BACKED", note_reader.BACKED)
print("markdown head:", note["markdown"][:600])

print("\n=== tree pane 00-04-10_pane0 ===")
every = tree_reader.ocr_rows(p("00-04-10_pane0.png"))
print("ocr rows:", len(every))
rows = tree_reader.tree_rows(every)
print("tree_rows kept:", len(rows))
for r in every[:50]:
    print(f"  y={r['y0']:5} x0={r['x0']:4} {r['text'][:60]}")
tree = tree_reader.read_tree(p("00-04-10_pane0.png"))
print("read_tree rows:", len(tree["rows"]), "verdict:", tree.get("layout_verdict"), "chrome dropped:", tree.get("chrome_rows_dropped"))
print("first/last kept:", tree["rows"][0]["name"] if tree["rows"] else None, "/", tree["rows"][-1]["name"] if tree["rows"] else None)

print("\n=== title strip 00-03-00_top_585_309 ===")
res, _ = eng(p("00-03-00_top_585_309.png"))
print("strip readings:", [(t, round(s,2)) for _, t, s in (res or [])])
texts = [t for _, t, _ in (res or [])][:6]
print("confirm:", verify_names.confirm_readings(p("00-03-00_top_585_309.png"), texts))

print("\n=== list pane 00-03-00_pane4: what the recogniser sees vs the blocks ===")
res, _ = eng(p("00-03-00_pane4.png"))
for b, t, s in (res or []):
    ys = [q[1] for q in b]; xs=[q[0] for q in b]; print(f"  y={int(min(ys)):5} x={int(min(xs)):5} {t[:70]}")
lst = columns.read_list(p("00-03-00_pane4.png"))
print("blocks:", [(b["header"], len(b["rows"])) for b in lst.get("blocks", [])])
