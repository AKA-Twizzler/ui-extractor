# Calibration notes — run 2, the geometry layer

Status: the layer runs end to end; rows and names recover; the arrow and
nesting thresholds are NOT yet locked. This file seeds the calibration.

## What is proven
- tesseract TSV gives stable rows and names; the y-order is exact.
- The same sidebar row yields the same pixel measurements across frames
  (00-02-09 / 00-03-29 / 00-07-09): cross-frame consensus works.
- The gap-based furniture filter removes the title bar and bottom noise.
- The indent signal lives in the pixels, not in tesseract boxes: the row's
  leftmost glyph (chevron for folders, page icon for files) and the name
  text start.

## Measured text-start x per row (3x crops, threshold 105, 3-col run, 0.22)
Root rows at x=40-42; "02 - Carson James" at 62; child band x=220..305.
The first-text-token x carries variable-width digit prefixes ("00 -", "01 -"),
which blur the step: the next calibration must measure the FIRST LETTER of
the name, not the first token.

## The looker cannot calibrate structure
The multimodal-looker, given the three strips, transcribed OUR vault's tree
(VAULT-INDEX, Active Priorities, ETHEREAL Voice Guide) onto Jared's sidebar,
with invented pixel numbers (24 px step, 29 px rows). Semantic reliance at
the structure level: its word steers nothing, not even calibration.

## Next calibration step
A debug-dump tool that, per row, prints the pixel profile of the name's
first letter (the run of bright columns), so the level clustering is set
from clean letter positions. Then lock: chevron template (from the
known-expanded "02 - Carson James" row) and the right template (from a known
collapsed folder), the indent step, and the checkbox/bullet thresholds.
