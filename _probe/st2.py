import sys; sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import cv2, numpy as np, machine, style_reader as sr, tree_reader, note_reader, json
base = "/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/"
# 1. the Finder list: look, bands, icons before rows
p = machine.here(base + "00-03-00_pane4.png")
img = cv2.imread(p)
print("look", sr.look(img))
b = sr.bands(img); print("bands", [(x["y0"], x["y1"], x["hue"], x["colour"]) for x in b])
rows = tree_reader.ocr_rows(p)
print("rows", len(rows))
ic = sr.icons_before(img, rows)
for r, i in zip(rows, ic):
    print(f'  {r["y0"]:5d} {r["x0"]:5d} {r.get("text","")[:28]!r:32} band={ (sr.band_of(b, r["y0"], r["y1"]) or {}).get("hue")} icon={i and (i["hue"], i["box"])}')
print("pictures", sr.pictures(img, [[r["x0"], r["y0"], r["x1"], r["y1"]] for r in rows])[:5])
# 2. the note pane: slant / underline / pitch per tesseract row
p2 = machine.here(base + "00-04-10_pane2.png")
img2 = cv2.imread(p2)
print("look2", sr.look(img2))
note = note_reader.read_note(p2)
big = cv2.imread(p2.replace(".png", "_3x.png"), cv2.IMREAD_GRAYSCALE)
mask = sr.ink_mask(big)
for r in note["rows"][:30]:
    cell = mask[r["y0"]:r["y1"], r["x0"]:r["x1"]]
    print(f'  slant={sr.slant(cell):5.1f} ul={sr.underline(cell, r["xh"])} pitch={(sr.pitch(cell, r["xh"]) or {}).get("family")} {r["text"][:50]!r}')
# 3. the pointer on the 00:03:00 frame
fr = cv2.imread(machine.here(base + "00-03-00.png"), cv2.IMREAD_GRAYSCALE)
print("pointer 00:03:00", sr.pointer(fr))
fr = cv2.imread(machine.here(base + "00-04-10.png"), cv2.IMREAD_GRAYSCALE)
print("pointer 00:04:10", sr.pointer(fr))
