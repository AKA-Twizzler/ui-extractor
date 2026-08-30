"""Why does the Finder table on works 00:07:29 come back as two blocks?

Print the blocks' row ranges, bands, and for the boundary rows the cells with
their boxes -- looking for a cell whose box spans two bands (an OCR merge of
name and date), which fails `belongs` one-cell-per-band and breaks the run.
"""
import sys
import cv2

sys.path.insert(0, ".")
import columns
import note_reader
import machine
from tree_reader import ocr_rows

PANE = "G:/Images/How Claude Code Actually Works/00-07-29_pane6.png"

bgr = cv2.imread(PANE)
bgr = machine.enlarge(bgr, 3)
big = PANE.replace(".png", "_probe3x.png")
cv2.imwrite(big, bgr)
gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
mask = note_reader.ink_mask(gray)

cells_in = [c for c in ocr_rows(big) if c["text"].strip()]
rows = columns.group_rows(cells_in)
tess = note_reader.tess_rows(big, gray)
space_w = columns.space_width(tess)
print(f"{len(rows)} rows, space_w {space_w:.1f}")
found, _ = columns.blocks(mask, rows, space_w)
for bi, (block_rows, corrs) in enumerate(found):
    bands = columns.bands_from(corrs, mask.shape[1])
    lo = rows.index(block_rows[0])
    hi = rows.index(block_rows[-1])
    print(f"\nblock {bi}: rows {lo}-{hi}, corridors {corrs}")
    print(f"  bands {bands}")
for i, r in enumerate(rows):
    marks = " | ".join(f"{c['text'][:26]}@{c['x0']}-{c['x1']}"
                       for c in r["cells"])
    print(f"  row {i:2}: {marks[:150]}")
