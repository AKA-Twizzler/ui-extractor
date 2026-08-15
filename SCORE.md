# Calibration score

Machine output against GROUND-TRUTH-TREE.md, the 00:02:09 sidebar, aligned on
"02 - Carson James". Reproduce with `python3 score.py <tree.json>`.

## Current

Pipeline: `capture.py` (burst + median stack, PNG) -> `tree_reader.py`
(structure from pixels) -> `verify_names.py` (second engine) -> `score.py`.

```
  names, exact             30/31
  names, ignoring spacing  30/31
  folder vs file           31/31
  depth                    31/31
  open vs closed           31/31
  ALL FOUR correct         30/31
```

The one row short is `Carson Al` / `Carson AI`: capital I and lowercase l are
the same shape in this font, so no recogniser can separate them from pixels.
It is reported as `ambiguous-glyph` with both readings kept, never guessed.

Cross-frame consensus over the three captured moments settles 37 of 40 names.
The 3 it leaves flagged are all the same capital-I problem.

## Previous, for comparison

The template-matching build (`ui_geometry.py`, superseded by `tree_reader.py`):

```
  names        28/31
  structure    17/31   -- all 15 folder rows missed the arrow entirely
```

It failed because it tried to learn the shape of an arrow from the picture,
and this picture contains no closed folder at the top level to learn from.
