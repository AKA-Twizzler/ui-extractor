#!/usr/bin/env python3
"""Point this at a video and get back what its interfaces show.

    python3 pipeline.py <video> [--every 10] [--limit 12]

It maps the video, captures one frame per distinct screen, and reads whatever
it can from each: the file tree where there is one, the text where there is
not. Everything it cannot settle is reported as unsettled rather than guessed.
"""
import os
import sys

import cv2
import numpy as np

import capture
import screenness
import spot
import chat_reader
import columns
import machine
import console_reader
import panes
import note_reader
import overlay
import transcript
import tree_reader
import verify_names


# Splitting a window into panes lives in panes.py and is used from there.
# This module carried its own simpler copy for a while, which only looked for
# a DRAWN border. Obsidian does not draw one between its sidebar and its note
# -- the boundary is a step in background colour -- so a window with the
# presenter's inset over it never split at all, and a sidebar and a note were
# read as one pane that was neither. panes.py also splits where no line of
# text crosses, which finds that boundary; one home, and the better one.
frame_regions = panes.frame_regions
write_box = panes.write_box

# Every reader that fell over during a run, so a run that limped says so at
# the end instead of looking clean.
STUMBLED = []


def guard(what, fn, *args, **kwargs):
    """Run one reader, and never let it end the run.

    A pass over the whole library is tens of thousands of panes, and one of
    them will always be the shape no reader expected. Measured the hard way:
    an entry with no name reached the chat reader, `sum(ch.isalpha() for ch in
    None)` raised, and a run that had already read half a video threw all of it
    away -- the traceback replaced the answer rather than joining it.

    So a reader that falls over costs its own pane and says so on the spot,
    and the count is repeated at the end. Nothing is swallowed: a failure is
    printed where the reading would have been, which is the same rule the rest
    of this build runs on -- refuse out loud rather than return a guess or
    return nothing.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as why:
        note = f"{what}: {type(why).__name__}: {why}"
        STUMBLED.append(note)
        print(f"    [this reader fell over and the run went on -- {note}]")
        return None


def already_drawn(lines, drawn):
    """Is this pane just the text that was already proved drawn on the picture.

    A thing is an overlay or it is a pane's own content; it cannot be both,
    and the record must not say both. On a live stream the caption block --
    "Everything dollar we make on / live tonight is going to St. Jude's /
    Children's Hospital and I am ..." -- was proved composited over the room
    by holding still while the shot moved, printed as that, and then read
    AGAIN out of the pane underneath it and printed as A FILE TREE. The same
    six lines, twice, under two labels that contradict each other.

    Which of the two is right is not in doubt. The overlay verdict is proved
    by behaviour over minutes of film; the tree verdict is a guess from
    left-aligned lines. So where a pane is mostly text this frame has already
    accounted for, it is not read again.
    """
    said = [ln.strip() for ln in lines if ln.strip()]
    if not said or not drawn:
        return False
    known = sum(1 for ln in said if ln in drawn)
    return known * 2 > len(said)


def say_pane(pane_path, pi, engine, drawn=()):
    """Read one pane every way there is, and print what it turned out to be."""
    def owned(lines):
        if not already_drawn(lines, drawn):
            return False
        print(f"  [pane {pi}: the text drawn on the picture, reported above]")
        return True

    tree = guard(f"tree reader, pane {pi}", tree_reader.read_tree, pane_path) or {}
    if tree.get("is_tree") and len(tree["rows"]) >= 5:
        if owned([r["name"] for r in tree["rows"]]):
            return True
        tree = guard(f"second engine, pane {pi}",
                     verify_names.verify, pane_path, tree) or tree
        print(f"  [pane {pi}: a file tree]")
        print(tree_reader.render(tree))
        flagged = [x for x in tree["rows"]
                   if x.get("name_status") not in ("confident", "reconciled")]
        if flagged:
            print("    unsettled: " + "; ".join(
                f"{x.get('name_primary')!r}/{x.get('name_second')!r}"
                for x in flagged))
        return True
    # a terminal first: it is the one screen that proves itself, since nothing
    # else sets every character on one width, and read as anything else it
    # loses the split between what Jared typed and what came back -- which is
    # most of what it says
    term = guard(f"terminal reader, pane {pi}",
                 console_reader.read_console, pane_path) or {}
    if term.get("is_console"):
        print(f"  [pane {pi}: a terminal]")
        for line in console_reader.render(term).splitlines():
            print("    " + line)
        return True
    # not a tree: a column view before a document, since a table read as prose
    # loses the pairing of value to heading
    lst = guard(f"columns reader, pane {pi}", columns.read_list, pane_path) or {}
    if lst.get("is_list"):
        print(f"  [pane {pi}: a list of columns]")
        for line in columns.render(lst).splitlines():
            print("    " + line)
        return True
    # a live stream's chat log, before the document reader, which would
    # otherwise take it for prose and lose who said what
    chat = guard(f"chat reader, pane {pi}",
                 chat_reader.read_chat, pane_path, engine=engine) or {}
    if chat.get("is_chat"):
        print(f"  [pane {pi}: a chat log]")
        for line in chat_reader.render(chat).splitlines():
            print("    " + line)
        return True
    # a document: the words AND the shape
    note = guard(f"document reader, pane {pi}",
                 note_reader.read_note, pane_path) or {"markdown": "", "backed": 0}
    # lines of TEXT, not lines of output: the fences round a properties block
    # are structure the reader emits, so counting them lets two garbled words
    # come back as a document. And enough of those lines must be lines the
    # OTHER engine read too. Every line here is already read twice and
    # reconciled; nothing had ever looked at the verdict, so a stream's
    # leaderboard came back as prose -- "# 3 & Dr. Paris Woods", "a @& Alex
    # Palencia" -- with one line in eight backed.
    if (note_reader.body_lines(note["markdown"]) >= 3
            and note["backed"] >= note_reader.BACKED):
        if owned(note["markdown"].splitlines()):
            return True
        print(f"  [pane {pi}: an open document]")
        for line in note["markdown"].splitlines():
            print("    " + line)
        return True
    res, _ = engine(pane_path)
    texts = [t for _, t, _ in (res or [])]
    # Nothing is dropped for being short. This used to skip any pane with
    # fewer than four readings, which is silent loss -- the worst kind,
    # because the output looks complete. On a slide of nine cards split into
    # three columns, the left column held three of them and was thrown away
    # without a word: "moonstone.co * 12k", "the tiny gem * 4k", "hearthstone
    # * 15k" simply were not in the answer. Whether a reading is worth
    # anything is what the confirmation below says, and it says it out loud.
    if not texts:
        return False           # nothing on it; the caller says so, once
    if owned(texts):
        return True
    # nothing else placed this pane, so there is no structure to stand behind
    # the words. Printing them as read is how "R78" came off Jared's
    # visualizer -- three faint marks one engine calls R78 and the other calls
    # Ris. The rule this build runs on is that a string enters the record only
    # when the instruments confirm it, so say which ones did.
    marked = guard(f"confirmation, pane {pi}",
                   verify_names.confirm_readings, pane_path, texts[:16])
    if marked is None:
        marked = [(t, False) for t in texts[:16]]
    sure = [t for t, ok in marked if ok]
    doubt = [t for t, ok in marked if not ok]
    print(f"  [pane {pi}: text, not a tree]")
    if sure:
        print("    " + " | ".join(sure))
    if doubt:
        print("    [only one engine read these] " + " | ".join(doubt))
    return True


def main():
    video = sys.argv[1]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 10
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 12
    # --at 00:14:30,01:02:00 reads exactly these moments and skips mapping the
    # video first. Everything below is untouched, which is the whole point: a
    # probe that took its own path would prove nothing about what this does.
    at = (sys.argv[sys.argv.index("--at") + 1].split(",")
          if "--at" in sys.argv else [])
    title = os.path.basename(os.path.dirname(video)) or "capture"
    out_dir = machine.here(f"/mnt/g/Images/{title}")
    cache = os.path.join(out_dir, "scan.json")

    print(f"=== {title} ===")
    if at:
        runs = [{"best": {"t": int(capture._to_seconds(s.strip()))}} for s in at]
        joined = False
        if "--limit" not in sys.argv:
            limit = len(runs)      # named moments are not silently dropped
        print(f"{len(runs)} moments named\n")
    else:
        samples = spot.scan(video, every, cache, rescan="--rescan" in sys.argv)
        every_run = spot.stretches(samples)
        # the words that go with each screen, joined on the one clock both
        # halves were stamped with -- see transcript.py
        joined = transcript.words_for(video, every_run) is not None
        runs = [r for r in every_run if r["call"] == "screen"]
        print(f"{len(runs)} distinct screens found; capturing "
              f"{min(limit, len(runs))}\n")

    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    standing = set()

    for r in runs[:limit]:
        secs = r["best"]["t"]
        ts = spot.hms(secs)
        try:
            path, how = capture.capture_moment(video, ts, out_dir)
        except RuntimeError as why:
            # a damaged patch is the file's problem, not this moment's, and
            # certainly not the other eleven moments' -- say so and go on
            print(f"--- {ts}  (no picture: {why}) ---\n")
            continue
        img = cv2.imread(path)
        if img is None:
            print(f"--- {ts}  (no picture: {path} would not open) ---\n")
            continue
        regions = guard(f"screenness at {ts}",
                        screenness.ui_regions, img, engine) or []
        share = sum(x["share"] for x in regions) * 100
        print(f"--- {ts}  ({how}; interface on {share:.0f}% of the frame) ---")
        if joined and r.get("said"):
            print(f"  [said while this screen was up]\n    {r['said']}")
        # Both kinds of overlay are read from the WHOLE frame, and before the
        # test for readable interface -- a live stream is mostly camera, and a
        # banner over a shot of the room is exactly the case that test rejects.

        # A panel is a rectangle floating over video, so it belongs to no pane
        # and splitting the frame would cut it in half.
        # Only the panels floating over VIDEO -- see overlay.floating, which
        # owns that question and says why.
        for panel in overlay.floating(
                (guard(f"panel reader at {ts}", overlay.read_overlays,
                       path, engine) or {"panels": []})["panels"],
                regions, img.shape[1], screenness.WORK_WIDTH):
            print("  [a panel drawn on the picture]")
            unsettled = set(panel.get("unsettled") or [])
            if panel["label"] and not unsettled:
                print(f"    {panel['label']}: {panel['value']}")
            else:
                for line in panel["lines"]:
                    mark = "  <- only one engine read this" if line in unsettled else ""
                    print(f"    {line}{mark}")

        # Text with no panel round it -- a banner, a lower third -- is proved
        # by watching its spot over minutes: an overlay holds still while the
        # picture behind it moves, and a sticker on the shelf does not. Asked
        # at every moment rather than once, because a banner comes and goes
        # and moves about the frame; each wording is reported the first time
        # it is proved, and text this cannot prove is simply not claimed.
        # and only where there IS a picture to be composited over. The
        # question is whether this text was drawn on top of the camera, which
        # on a frame that is mostly interface has no meaning -- everything on
        # a screen recording is drawn. Measured: the two frames carrying the
        # banner are 25% and 10% interface, and the two where a fragment of
        # the room crept in are 67% and 100%.
        # every wording proved drawn at THIS moment, whether or not it is new:
        # an earlier moment having already reported it does not make it the
        # pane's own text now -- see already_drawn
        #
        # Sending these through floating(), the way the panels go, was tried
        # and is WRONG -- kept here because the next person to look at this
        # will think of it too. A Mac desktop wallpapered with a PHOTOGRAPH,
        # carrying a Finder window, a terminal and two documents, measures 15%
        # interface and opens this gate, and "Size", "Locations" and "Har"
        # come back as text drawn on the camera. Asking where each one SITS
        # looks like the fix. Measured, it drops one of those three and it
        # also drops jaredrhod.com from two of the three live streams -- the
        # one banner this whole instrument exists to admit -- because a
        # screenness box happened to cover it. The boxes are wrong in both
        # directions at once: too few on a wallpapered desktop, too generous
        # on a stream. Anything gated on them inherits that, so the fix is not
        # here; it is in the regions themselves.
        drawn = set()
        for found in ((guard(f"standing text at {ts}", lambda: overlay.standing_text(
                overlay.frames_across(video, secs,
                                      workdir=os.path.join(out_dir, "_looks")),
                engine=engine)) or []) if share < 50 else []):
            drawn.add(found["text"].strip())
            if found["text"] in standing:
                continue
            standing.add(found["text"])
            print("  [drawn on the picture, standing while the shot moved]"
                  f"\n    {found['text']}")

        if not regions:
            print("    no readable interface at full size\n")
            continue

        # the frame's windows first, each split into ITS panes, and then the
        # desktop no window covers -- a frame holding one window comes back
        # exactly as it did when this only cut vertical strips
        # Every region the splitter found is accounted for. A pane that says
        # nothing used to print nothing, and so did a pane the writer refused
        # -- on one frame four of seven were invisible that way. No text was
        # lost by it, but nothing in the output told a reader whether a pane
        # held nothing or was never looked at, and those are not the same
        # claim. This build's rule is that refusal is an answer and silence is
        # not, so the quiet ones are named, on one line rather than four.
        quiet, unwritten = [], []
        for pi, box in enumerate(guard(f"regions at {ts}", frame_regions,
                                       img, engine=engine) or []):
            pane_path = os.path.join(
                out_dir, f"{ts.replace(':','-')}_pane{pi}.png")
            if write_box(img, box, pane_path) is None:
                unwritten.append(pi)
                continue
            if not say_pane(pane_path, pi, engine, drawn):
                quiet.append(pi)
        if quiet:
            print(f"  [panes {', '.join(map(str, quiet))}: looked at, "
                  "nothing readable on them]")
        if unwritten:
            print(f"  [panes {', '.join(map(str, unwritten))}: too small to "
                  "cut out, not read]")
        print()

    if STUMBLED:
        print(f"[{len(STUMBLED)} reader(s) fell over in this run and were "
              "stepped over]")
        for note in STUMBLED:
            print("   " + note)


if __name__ == "__main__":
    main()
