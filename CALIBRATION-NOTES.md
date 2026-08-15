# How the tree is read, and what had to be learned to get there

Status: the structure read is exact on the fixture — folder vs file, depth,
and open vs closed all 31 of 31. Names are 30 of 31, the last being a glyph
no recogniser can decide. `ui_geometry.py` is superseded by `tree_reader.py`.

## The method

The text comes from OCR, the structure comes from pixels, nothing comes from
a model's judgment.

Obsidian draws one faint vertical guide line per ancestor level, so:

```
  depth            = how many guide-line columns the row shows
  collapsed folder = a wide glyph between the last guide line and the name
  expanded folder  = the next row is deeper than this one
  file             = neither
```

Each of those is a count or a comparison, so there is nothing to tune.

## The four rules that make it self-calibrating

Only one number could have been a magic constant — how far above its
background a pixel must sit to count as part of a line. It is measured, not
set, by sweeping it and keeping the value that satisfies rules that are
always true of a rendered tree:

1. **Prefix.** A row's guide lines are the FIRST k columns, never with a gap.
2. **Single step.** Depth rises by at most one from a row to the next, since
   a child cannot be drawn without its parent above it.
3. **Even spacing.** The guide columns lie on one regular grid, because a
   tree indents every level by the same amount.
4. **Not every row.** A column drawn beside every row is a border, not a
   guide line; a guide line is missing from the shallowest rows.

Among the settings that satisfy all four, the one resolving the most levels
wins, ties broken by the width of the plateau of settings that agree with it.

## Lessons, dearly bought

1. **The looker cannot do this, at either level.** Given the frames it
   transcribed OUR vault's tree onto Jared's sidebar and invented pixel
   measurements to go with it. Its word steers nothing, not even calibration.
2. **Brightness is the wrong test for a line; coverage is the right one.** A
   guide line stands above its background down the whole row, a chevron only
   part of it. Using brightness alone let a faint arrow fragment pass as a
   guide line and shifted every depth below it.
3. **Subtract the background before measuring.** The open file's row carries
   a selection highlight brighter than the guide lines it hides. Removing
   each row's own background with a horizontal opening makes the read survive
   it; absolute brightness cannot.
4. **Position cannot separate a border from a guide line.** The first guide
   line sits to the LEFT of a root row's name, because a root's own arrow
   occupies that space. Height and presence separate them; x does not.
5. **Pick the best candidate, not the first.** The row-pitch filter that
   isolates the tree from window chrome must take the closest match to the
   pitch, or a ribbon icon a few pixels off steals the link and the real row
   below it is silently dropped.
6. **Stacking beats sharpening.** On a still screen the burst's median cancels
   compression noise for free. Where the screen moves, stacking would smear
   it, so the sharpest single frame is used instead — decided by measurement,
   not by hand.
7. **The pixel source was NOT the bottleneck, contrary to expectation.** JPEG
   versus lossless PNG, and single frame versus 60-frame stack, moved OCR mean
   confidence by 0.2 points and recovered all 31 names either way. Lossless is
   kept because it is free and strictly better, but the win was structural.
8. **Two engines disagree in useful ways.** Tesseract and RapidOCR miss
   different names. Neither is trusted alone: identical readings are
   confident, same letters with more spaces reconcile to the spaced one (OCR
   drops spaces, it never invents them), and anything else is flagged.
9. **Some characters are undecidable and must be said so.** Capital I,
   lowercase l and the digit 1 are one shape in a UI font. Those rows are
   marked `ambiguous-glyph` carrying every candidate reading. Guessing there
   is exactly the invention this whole build exists to prevent.
