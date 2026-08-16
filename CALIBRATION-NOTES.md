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
14. **A column view fills its columns on EVERY row it covers.** A majority is
    not enough. A terminal recording with the presenter's camera inset in the
    corner came back as a confident two-column table of prose: the inset
    leaves a blank gap, OCR finds text on the cap and the shirt, and those
    fragments fill the far band on half the rows. The cost of the strict rule
    is that a table with genuinely empty cells is refused, which is the right
    way round — refusing falls back to reading the pane as prose, which loses
    the pairing but invents nothing.
15. **The tie measure needs flat area, so it cannot judge a word.** Trying to
    tell that same camera text from interface text by its exact-pixel ties
    fails at both scales: a band is mostly flat background and scores like a
    screen wherever the inset sits, and a tight text box is mostly ink edges,
    where screen text measured 0.21–0.53 and camera text 0.07–0.44. It works
    on regions, and only on regions.
16. **One home for the splitter, and it must not be the simpler one.**
    pipeline.py carried its own copy that looked only for a DRAWN border.
    Obsidian does not draw one between its sidebar and its note — the
    boundary is a step in background colour — so a window did not split at
    all and the two panes were read as one that was neither. panes.py also
    splits where no line of text crosses, and finds it.
17. **Do not paint the camera out before splitting.** The presenter's inset
    sits ON the interface, and removing it first looks obvious. The painted
    patch has hard edges, and those read as pane borders: the sidebar split
    in two and lost a row. The inset needs no handling at all, because rows
    found on a cap and a shirt do not sit on the tree's row pitch and are
    dropped as chrome already.
18. **Fit the character lattice; never average it.** A terminal's advance
    taken as a median of per-word widths came out 78.5px against a true
    82.3px, and the 4.7% error accumulates: by the seventeenth character of
    a prompt the cell boundary has walked half a glyph, and every letter
    after that is cut from the wrong box. Word edges cannot fix it either —
    a box hugs the ink, so it sits inside its cell by however much that
    particular letter's bearing happens to be, and a least-squares fit to
    those edges lands 0.16 cell out. The ink is periodic: the profile of ink
    down each column beats at the advance, its autocorrelation gives the
    period, and the phase is wherever that profile is quietest. Two
    independent methods agreeing on 82.3 is what made it safe to use.
19. **Cut cells on the baseline, never on the row box.** A row is boxed
    around whichever ascenders and descenders it happens to contain, so the
    same letter in two rows comes out at two different heights and matches
    nothing. The baseline does not move: most glyphs end on it at once, so
    it is the steepest fall in the row's ink. With cells cut on the box,
    same-letter and different-letter distances were indistinguishable
    (medians 0.156 and 0.164). Cut on the baseline they separate cleanly
    (0.012 against 0.110) — the difference between an instrument and noise.
20. **The middle of a word box, never its edges.** Even on an exact lattice,
    a "%" is drawn wide enough that its box crosses into the cell before it,
    and taking the column from the left edge puts the prompt marker one cell
    early and swallows the space in front of it. The middle of a word of
    known length gives the column back exactly. Where a run of written-on
    cells is exactly as long as the word, that settles it outright instead.
21. **A screen's own font can settle letters, within limits worth stating.**
    Cells whose pixels match are the same character, so a doubted cell can be
    read off its twins — which is how "~/.zshre" became "~/.zshrc" without
    preferring an engine. What does NOT work, each tried and measured: a
    majority vote inside a radius (merges "h" with "n", since they stand
    0.017 apart while true twins stand 0.011); unanimity among the three
    nearest (flips single cells, 93.9% down to nothing gained); comparing
    shrunk cells to save time (blurs away the very ascender that separates
    "h" from "n"). What works is the nearest match, inside a radius the frame
    measures for itself, and only when the reading that would replace the
    letter appears somewhere else on screen — a screen carries a few glyphs
    drawn once each, a warning sign, a bullet, a tick, and left alone they
    match each other, every one of them a lone blob. Worth 92.2% to 94.2% on
    the fixture, decided by scoring rather than by eye.
22. **Two marks for the edge of a frame, not one.** Jared's recordings zoom
    in, so a terminal is often wider than the picture. A glyph the frame cut
    through has ink in the very last column of pixels and is certainly
    incomplete; a line cut in the space BETWEEN two glyphs leaves nothing
    bisected and reads as whole. Reporting both as "cut" calls a sentence
    that merely ends in the last column a lie; reporting only the first
    presents two thirds of a command as the whole of it. So: "cut" for
    proven, "edge" for possible, and the fixture grades both.
23. **Find the columns from the rows that share them; find the ROWS after.**
    A table has rows that do not share its corridors, and each for a real
    reason rather than a fault: Finder left-aligns the heading "Size" over
    sizes it right-aligns, so the heading crosses the corridor its own column
    stands on; the selected row is drawn white on a green fill, which changes
    what counts as blank across it; a long file name runs within two spaces
    of the next column and closes the corridor for that row alone. Trying to
    fit them into the corridor search is what failed three times before —
    ranking blocks by rows, by area, and letting failed blocks claim nothing
    — each collapsing the columns, breaking the dashboard, or turning prose
    into a table. Once the columns are settled the question gets simpler and
    the corridor test never has to bend: does this neighbouring row fill every
    column, one cell to each, with nothing left over. One cell to each is what
    keeps the path bar out — its eight crumbs land two to a column — and
    nothing left over is what keeps the toolbar out. Where two tables both
    want a row, the one with more columns takes it, which is the order the
    tables were chosen in; a table left too short to be one is dropped, and
    that is what dissolved a spurious two-column table holding the last two
    files of a four-column one.
24. **On a live stream, find the PANEL, never classify the text.** A frame
    holding a "jaredrhod.com" banner the application drew and a "FALSE"
    sticker on the shelf behind Jared defeats every measure tried on the text
    itself, each one recorded here so it is not tried again. Exact-pixel ties,
    which separate a screen recording from a camera everywhere else in this
    build, put the banner BELOW the sticker (0.24 against 0.44) — over moving
    video a banner's own soft edges break ties. Motion between frames a second
    apart put the sticker (25) below the chat (159 and up), because the chat
    scrolls: drawn is not the same as still. Flat colour found nothing, the
    room being dim enough that the frame's median local deviation was 0.6 grey
    levels. The exact painted colour found the panel on one frame and not the
    other, because the room is lit green and shares the panel's green. What
    works is the one thing an application does and a room cannot: it draws a
    RECTANGLE, two horizontal steps and two vertical ones each running dead
    straight for hundreds of pixels at exactly one x or one y. Two card edges
    with video between them make a rectangle just as square, and the fill
    tells them apart — the cards measured 0, 0 and 1 grey levels of spread,
    the video between them 5. Free-floating text with no panel round it is
    judged separately, and by a different question — see lesson 26.
25. **Cut a row at a gap too wide to be a space; do not throw it away.** The
    recogniser returns a scan LINE, not a column, so a slide on the left of a
    frame and a chat log on the right come back as one row with a quarter of
    the picture in between. The chat's margin is then never found, its own
    lines are judged against the slide's margin, and three bullet points and
    their captions were reported as things people had said. The width that is
    no longer a space was already measured for telling writing from scattered
    marks; cutting there rather than rejecting the row keeps both halves.
26. **Ask how text BEHAVES, not how it looks.** Seven measurements failed to
    tell a drawn banner from a sticker on the shelf: exact-pixel ties, motion
    over a second, flat colour, the exact painted colour, the purity of the
    ink, the sharpness of the glyph edges, the evenness of the stroke. Several
    failed backwards, and the reason is worth holding on to — the sticker is
    printed matter photographed close up, so it is crisper, purer and more
    even than a banner drawn over moving video. Every property that sounds
    like "drawn" belongs to the sticker here. What separates them is not the
    text at all but its relationship to the ground it sits on, watched over
    MINUTES rather than seconds: an overlay is composited on top, so the
    picture behind it changes and it does not; a sticker is part of that
    picture, lit by the same lamps and walked in front of by the same person.
    So: drawn, if the glyphs changed no more than the ground around them, and
    only where the ground changed at all — nothing is proved by standing still
    in front of something that also stood still. Measured over ten minutes on
    two streams, the banner gave 19 against 32 and 11 against 29, the sticker
    111 against 72 and 86 against 51, and on both frames the banner was the
    only text admitted. Text the test cannot prove is left unclaimed rather
    than called scenery: a chat line scrolls away and a counter ticks over, so
    both fail it though both are drawn, and both have their own readers.
27. **Move the work to the data, and keep one file that knows where it is.**
    This build reads frames off a Windows drive and writes pictures back to
    one, thousands of times in a run, and from Linux every crossing is
    answered by a Windows process — so the Linux side slows Windows itself
    rather than only itself. It now runs from Windows, and `machine.py` is
    the ONLY file that knows which platform it is on: every path stays
    written the one way in the code and is translated in that one place.
    The alternative — a platform test at each of the seven places a drive
    was named — is the same fact in seven homes, and the seventh is the one
    that gets forgotten.
28. **A moved instrument is not the same instrument until it is scored
    again.** The move looked clean: the working tree matched the commit byte
    for byte, every module imported, and the tree fixture came back at 30/31
    names with all three structure counts perfect, identical to Linux down to
    which row it misses. The terminal fixture did not — 336 of 360 characters
    against 339 — because the published tesseract for Windows is 5.4.0 and
    Ubuntu ships 5.3.4, and the two are wrong in different places. Nothing in
    the method moved; the recogniser did. Both numbers are recorded rather
    than the better one, because a score that quietly names a different
    machine is not a score.

    Two real faults hid inside that gap and would have been read as engine
    noise. Windows decodes a pipe in cp1252 unless told, so tesseract's UTF-8
    came back with one curly quote as three wrong characters. And Windows
    writes its console in cp1252 too, so the first run did not print a wrong
    warning triangle — it stopped with an encoder error partway through the
    answer. Both are one-line fixes, and both are invisible until a frame
    carries a character outside the alphabet.
29. **A tree's indentation IS its depth — fit that line and measure the
    worst row.** Two faults stood open: a live stream's chat log came back as
    a file tree with folders in it (`˃ DavidThuku-89`), and so did a desktop's
    menu bar (`˃ Clock`, `˃ File Edit`). Two measurements had already failed
    to separate them — the x-alignment of rows within one depth, and the ink
    in the gutter where a chevron would be.

    What works is the definition of the thing. A tree is exactly a layout
    whose indentation carries depth: rows at one depth start at one x, and the
    step from each depth to the next is one indent. Fit `x = base + depth *
    indent` through the rows and take the worst row's distance from it. In ROW
    HEIGHTS, which the frame gives itself — a fixed pixel count means
    something different on a 640-wide crop and a 3840-wide desktop. Real
    sidebars measure 0.55 and 0.71; the chat log 3.19, the menu bar 21.5.

    A near miss worth keeping: row RHYTHM looked like the answer first, since
    a tree draws every row at one height. It kills the menu bar (gaps of 0, 1,
    2, 323, 2592 pixels) but not the chat, whose lines are evenly spaced
    because a chat log is a list too. And taken carelessly it runs backwards —
    with the pitch read from the smallest gap, two rows a pixel apart make
    every gap a whole multiple of one pixel, and the false tree scored a
    perfect 0.000 against the real sidebar's 0.109. The pitch has to come from
    the median gap, never the smallest.
30. **A comparison needs a scale, or it proves nothing.** The test for text
    drawn on a picture was "the glyphs changed no more than the ground around
    them", and it was right as far as it went — on two live streams it admitted
    the `jaredrhod.com` banner and refused the `FALSE` sticker on the shelf.
    Run against a third video it admitted the sticker AND six fragments of the
    room: BEST, CALTY, BITCH, SOM, PEOPLE, XING. Every one of them had moved
    enormously — glyphs changing 140 to 175 where the banner changes 13 to 21 —
    and passed only because the wall behind them moved slightly more.

    A ratio with no scale under it is satisfied by two large numbers as easily
    as by two small ones. The missing half is the premise itself: drawn text
    does not move. So it must also be stiller than the frame's own median,
    which is a second comparison rather than a second threshold — the frame
    supplies the number. Banner 21 against a median of 37, and 13 against 40;
    sticker 48 against 40, and 161 against 52.

    Worth keeping about how it was found: this only surfaced because the whole
    pipeline was run end to end on a video it had never been run on. Neither
    fixture covers it, and the frame that broke it was not a hard frame — it
    was a man sitting in a room with posters behind him.
31. **Count what was READ, not what was written out.** A stylised heads-up
    display gave the recogniser decorative graphics, and it returned "we Me Bs:
    VE Ze Ss" and "ub: LN CONNECTED" for them. The note reader wrapped those
    two garbled lines in the `---` fences of a properties block, and the gate
    that asks whether there is enough here to be a document counted four lines
    and said yes. The fences are structure the reader emits; they are not
    something it read. Counting only lines carrying text, the fragment gives
    two and is refused, while the real note gives seven and the browser page
    beside it four.

    Rejected on the way, with numbers, so it is not tried again: the
    recogniser's own CONFIDENCE does not separate garbage from text here. A
    real note reads at a median 0.855, a real chat log 0.856, a real sidebar
    0.852 — and the two heads-up fragments at 0.798 and 0.825. It is
    confidently wrong, which is the failure this whole build is built around.
32. **Ask a question only where it means something.** Even with a scale under
    it, the test for text drawn on a picture kept admitting "SOM", a fragment
    of a poster, from a frame that was 100% interface — a full screen
    recording of Obsidian. Two more measurements failed to catch it, and both
    failed the same way: its glyphs changed 79.5 against a ground of 134 and a
    frame median of 86, and 1.77 times the frame's still floor, where the real
    banner measures 2.1 times its own.

    The mistake was not the measure, it was asking at all. "Was this text
    composited over the camera" has no meaning on a frame with no camera in
    it: everything on a screen recording is drawn. The frames carrying the
    banner are 25% and 10% interface; the two where the room crept in are 67%
    and 100%. So the test runs only where the frame is more picture than
    interface, which is a comparison the build already measures for other
    reasons.
