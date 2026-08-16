# Calibration score

Machine output against GROUND-TRUTH-TREE.md, the 00:02:09 sidebar, aligned on
"02 - Carson James". Reproduce with:

```
python3 verify_names.py <sidebar.png> --json tree.json
python3 score.py tree.json
```

## The tree

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

The single engine alone reads 26 of 31 names exactly; the five it misses are
all lost spaces, which the second engine restores. Structure does not depend
on either engine.

## Where the other two instruments stand

There is no numeric fixture for these yet — they are checked against the
frame they came from, by eye, until Tristan sets one.

`note_reader.py`, on the note at 00:07:30 of *How To Set Up Claude Code With
Obsidian*: properties recovered as frontmatter, all three heading levels in
the right places, bullets in the right places, wrapped lines rejoined. What
remains wrong is character-level and belongs to the recogniser, not the
method: one lost space inside a word, and a rendered arrow read as `>`.

The same reader on the note at 00:02:30 of the same video returns its two
headings and no invented ones.

`columns.py`, on the metrics dashboard at 00:00:20 of the same video: three
card bands, every value paired to its own heading, including two large
figures the line engine missed entirely. It correctly refuses the prose pane,
giving the reason.

Not yet proven, for want of a frame holding one: a Finder-style window with
Name, Date Modified, Size and Kind; and a file tree drawn in a light theme.
`hunt.py` sweeps a library for both.

## Previous, for comparison

The template-matching build (`ui_geometry.py`, superseded by `tree_reader.py`):

```
  names        28/31
  structure    17/31   -- all 15 folder rows missed the arrow entirely
```

It failed because it tried to learn the shape of an arrow from the picture,
and this picture contains no closed folder at the top level to learn from.
