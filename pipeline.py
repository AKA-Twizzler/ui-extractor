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


def say_pane(pane_path, pi, engine):
    """Read one pane every way there is, and print what it turned out to be."""
    tree = guard(f"tree reader, pane {pi}", tree_reader.read_tree, pane_path) or {}
    if tree.get("is_tree") and len(tree["rows"]) >= 5:
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
        return
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
        return
    # not a tree: a column view before a document, since a table read as prose
    # loses the pairing of value to heading
    lst = guard(f"columns reader, pane {pi}", columns.read_list, pane_path) or {}
    if lst.get("is_list"):
        print(f"  [pane {pi}: a list of columns]")
        for line in columns.render(lst).splitlines():
            print("    " + line)
        return
    # a live stream's chat log, before the document reader, which would
    # otherwise take it for prose and lose who said what
    chat = guard(f"chat reader, pane {pi}",
                 chat_reader.read_chat, pane_path, engine=engine) or {}
    if chat.get("is_chat"):
        print(f"  [pane {pi}: a chat log]")
        for line in chat_reader.render(chat).splitlines():
            print("    " + line)
        return
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
        print(f"  [pane {pi}: an open document]")
        for line in note["markdown"].splitlines():
            print("    " + line)
        return
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
        return
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
        for panel in (guard(f"panel reader at {ts}",
                            overlay.read_overlays, path, engine)
                      or {"panels": []})["panels"]:
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
        for found in ((guard(f"standing text at {ts}", lambda: overlay.standing_text(
                overlay.frames_across(video, secs,
                                      workdir=os.path.join(out_dir, "_looks")),
                engine=engine)) or []) if share < 50 else []):
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
        for pi, box in enumerate(guard(f"regions at {ts}", frame_regions,
                                       img, engine=engine) or []):
            pane_path = os.path.join(
                out_dir, f"{ts.replace(':','-')}_pane{pi}.png")
            if write_box(img, box, pane_path) is None:
                continue
            say_pane(pane_path, pi, engine)
        print()

    if STUMBLED:
        print(f"[{len(STUMBLED)} reader(s) fell over in this run and were "
              "stepped over]")
        for note in STUMBLED:
            print("   " + note)


if __name__ == "__main__":
    main()
