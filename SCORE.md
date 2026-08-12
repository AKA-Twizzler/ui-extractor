# Calibration score — first fixture-aligned rerun

Machine output vs GROUND-TRUTH-TREE.md (00:02:09 strip, aligned on Carson James):

- names: 28/31 (3 misses = icon-junk glued to the name, OCR merges)
- structure (kind + depth): 17/31
  - all 15 folder rows missed the triangle pass (kind wrong)
  - depth wrong on the junk-prefix rows (Assets, Buckaroo, Books, Courses,
    and the deeper folder branch)
  - files Beyond..VideoLibrary and the 8 campaign notes: full match (NKD)

Next targets: (1) the triangle templates from the fixture rows themselves
(Buckaroo = expanded, Books = collapsed); (2) clean x-anchors that strip the
junk prefixes before depth estimation.

Status: calibration loop live; score = the rerun verdict.
