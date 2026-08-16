# How a screen is read, and what had to be learned to get there

Three instruments, one law: the text comes from OCR, the structure comes from
pixels, and nothing comes from a model's judgment.

    tree_reader.py    a file tree      -> names, depth, folder/file, open/closed
    note_reader.py    an open document -> markdown, with its shape
    columns.py        a list or table  -> cells paired to their headings

Each refuses out loud when it is handed something it cannot read, rather than
returning a confident answer to the wrong question.

Status: the tree read is exact on the fixture — folder vs file, depth, and
open vs closed all 31 of 31. Names are 30 of 31, the last being a glyph no
recogniser can decide. `ui_geometry.py` is superseded by `tree_reader.py`.

## The tree

Obsidian draws one faint vertical guide line per ancestor level, so:

```
  depth            = how many guide-line columns the row shows
  collapsed folder = a wide glyph between the last guide line and the name
  expanded folder  = the next row is deeper than this one
  file             = neither
```

Each of those is a count or a comparison, so there is nothing to tune.

### The four rules that make it self-calibrating

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

Among the settings that satisfy all four, the one resolving the most guide
columns wins, then the most total depth, then the widest plateau of settings
that agree with it.

## The open note

Formatting is RENDERED, so there is no `#` to find and no `- [ ]` to find.
Every mark is measured instead:

```
  heading   the row's x-height against the body's, clustered; the distinct
            sizes above the body ARE the levels, in order
  bold      stroke thickness, as the mean width of a run of ink
  bullet    a drawn blob in the gutter; a checkbox is a drawn box
  number    the application draws "1." as text, so OCR reads it
  indent    where the row's text starts, against the leftmost body row
```

x-height, not the height of the OCR box: a line with a "g" in it measures
taller than the same size without one. Everything is measured on a 3x
enlargement, because at native size a stroke is two or three pixels and the
number can only land on whole values, which cannot separate bold from body.

Order of operations is part of the method, not an implementation detail:
markers are found FIRST so a bullet is never swallowed as the tail of the
line above it; wraps are joined ONCE; only then are sizes clustered into
ranks.

## The list or table

A tree carries its meaning in its indentation. A list carries it sideways,
and read row by row the pairing of a value to its heading is lost before the
reading starts. The instrument is the same shape as the guide lines:

```
  a column boundary is a vertical corridor of blank pixels
  that no row's text crosses
```

Prose cannot hold such a corridor open — a word may end anywhere and the next
line begins again at the margin. A column view cannot close one, because the
application reserves that space and clips text that would reach it.

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
   drops spaces, it never invents them), and anything else is flagged. They
   also specialise — the cell engine is primary for short strings, the line
   engine for prose, and on one dashboard the cell engine read large figures
   the line engine missed entirely.
9. **Some characters are undecidable and must be said so.** Capital I,
   lowercase l and the digit 1 are one shape in a UI font. Those rows are
   marked `ambiguous-glyph` carrying every candidate reading. Guessing there
   is exactly the invention this whole build exists to prevent.
10. **A tolerance is a bug waiting for its frame.** Twice a rule written as
    "near enough" failed on the next window: a wrapped line recognised by
    ending near the right margin lost every wrapped HEADING, because a
    heading is set in bigger type and wraps far short of where prose wraps;
    and a heading rank assigned by a one-sided cutoff dropped the heading
    sitting a pixel under it. Both were replaced by questions with no
    tolerance in them — would the next line's first word have FITTED, and
    which size is this row CLOSEST to.
11. **Measure the row, not the line.** A prose line carrying an inline code
    span measured as tall as a heading, because the span is set in another
    face and its ink lands outside the row's own band. A heading is uniformly
    larger — every word of it — so a row's size is the median of its words'.
12. **More resolved depth is better, not just more columns.** A contrast
    margin can find every guide column across a pane and still lose a faint
    line on ONE row. That flattens the row and costs the folder above it its
    open-or-closed state. A missed line can only make a row shallower; an
    invented one breaks the prefix rule and is thrown out before ranking.
13. **A full-width rule is not a column boundary's enemy by accident.**
    Applications draw section rules on the same line as the section title,
    laying ink clean across every corridor. Corridors are therefore asked of
    a RUN of consecutive rows, not of the whole pane, which also makes a grid
    of cards read as several tables without a rule written for that case.
