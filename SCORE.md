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

## The terminal

Machine output against GROUND-TRUTH-CONSOLE.md, the 00:02:42 frame of
*Install Claude Code and-or the AI Memory Vault*. Reproduce with:

```
python3 score_console.py <frame.png>
```

```
  characters               339/360  (94.2%)
  typed vs output            9/9
  cut marks                  9/9
```

Read from the full frame, presenter's camera inset and all — no hand-made
crop, no pane splitting needed, because the monospace test carries it.

What the remaining 21 characters are, so nobody chases the wrong one. Ten are
the top line, `Next: Run claude --help to get started`, which the line engine
mangles and the cell engine does not return at all; it is the topmost row of
the frame and half of it is drawn in colour. Six are the `⚠`, `●` and `✅`
that stand at the head of three lines — each drawn exactly once, so the
font has nothing to compare them against and they are left as read. The rest
are the `[` that opens each prompt, which the line engine reads as a curly
quote every time, and one inserted digit in `.1local`.

Turning the font consensus off scores 92.2%, which is how the 94.2% was
decided; see lesson 21 for the four rules that were tried and rejected.

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

Known gap, on a frame outside the fixture: at 00:06:00 the sidebar reads all
35 rows with every depth and every open-or-closed state matching the frame,
except one collapsed folder ("Courses") whose chevron is too faint at the
chosen contrast margin and comes back as a file. It is not chased, because
the fix — testing every row at the chevron column learned from its depth —
can turn a file INTO a folder, and inventing a folder is the worse error.

`columns.py` on a real Finder window -- found by `hunt.py`, at 00:07:00 of
*How Claude Code Actually Works*: thirteen files with Name, Date Modified,
Size and Kind, every value paired to the right column, including the names
the application itself truncated ("project_ship...ation_fix.md").

Known gap on that window: the heading ROW is not attached, so the columns are
named after the first file instead of "Name / Date Modified / Size / Kind",
and the selected row above it is left out of the block. The cause is a real
property of the window: Finder left-aligns the heading "Size" while
right-aligning the sizes themselves, so the heading crosses the very corridor
its own column stands on, and no run of rows containing it can keep that
column. Three ways to attach it were tried and each cost more than it gained
-- ranking candidate blocks by rows, by area, and taking the heading from the
row above while blocks that fail validation claim nothing. Each one either
collapsed the four columns into two, broke the dashboard, or made a page of
prose read as a table. The pairing is right; only the column NAMES are a row
out, and that is visible rather than silent.

Not yet proven, for want of a frame holding one: a file tree drawn in a light
theme. `hunt.py` sweeps a library for it.

## Previous, for comparison

The template-matching build (`ui_geometry.py`, superseded by `tree_reader.py`):

```
  names        28/31
  structure    17/31   -- all 15 folder rows missed the arrow entirely
```

It failed because it tried to learn the shape of an arrow from the picture,
and this picture contains no closed folder at the top level to learn from.
