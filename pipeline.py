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
pane_columns = panes.pane_columns
write_pane = panes.write_pane


def main():
    video = sys.argv[1]
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 10
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 12
    title = os.path.basename(os.path.dirname(video)) or "capture"
    out_dir = f"/mnt/g/Images/{title}"
    cache = f"{out_dir}/scan.json"

    print(f"=== {title} ===")
    samples = spot.scan(video, every, cache, rescan="--rescan" in sys.argv)
    every_run = spot.stretches(samples)
    # the words that go with each screen, joined on the one clock both halves
    # were stamped with -- see transcript.py
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
        path, how = capture.capture_moment(video, ts, out_dir)
        img = cv2.imread(path)
        regions = screenness.ui_regions(img, engine)
        share = sum(x["share"] for x in regions) * 100
        print(f"--- {ts}  ({how}; interface on {share:.0f}% of the frame) ---")
        if joined and r.get("said"):
            print(f"  [said while this screen was up]\n    {r['said']}")
        # Both kinds of overlay are read from the WHOLE frame, and before the
        # test for readable interface -- a live stream is mostly camera, and a
        # banner over a shot of the room is exactly the case that test rejects.

        # A panel is a rectangle floating over video, so it belongs to no pane
        # and splitting the frame would cut it in half.
        for panel in overlay.read_overlays(path)["panels"]:
            print("  [a panel drawn on the picture]")
            if panel["label"]:
                print(f"    {panel['label']}: {panel['value']}")
            else:
                for line in panel["lines"]:
                    print(f"    {line}")

        # Text with no panel round it -- a banner, a lower third -- is proved
        # by watching its spot over minutes: an overlay holds still while the
        # picture behind it moves, and a sticker on the shelf does not. Asked
        # at every moment rather than once, because a banner comes and goes
        # and moves about the frame; each wording is reported the first time
        # it is proved, and text this cannot prove is simply not claimed.
        for found in overlay.standing_text(
                overlay.frames_across(video, secs,
                                      workdir=f"{out_dir}/_looks"),
                engine=engine):
            if found["text"] in standing:
                continue
            standing.add(found["text"])
            print("  [drawn on the picture, standing while the shot moved]"
                  f"\n    {found['text']}")

        if not regions:
            print("    no readable interface at full size\n")
            continue

        for pi, (px0, px1) in enumerate(pane_columns(img, engine=engine)):
            pane_path = f"{out_dir}/{ts.replace(':','-')}_pane{pi}.png"
            if write_pane(img, px0, px1, pane_path) is None:
                continue
            tree = tree_reader.read_tree(pane_path)
            if tree.get("is_tree") and len(tree["rows"]) >= 5:
                tree = verify_names.verify(pane_path, tree)
                print(f"  [pane {pi}: a file tree]")
                print(tree_reader.render(tree))
                flagged = [x for x in tree["rows"]
                           if x["name_status"] not in ("confident", "reconciled")]
                if flagged:
                    print("    unsettled: " + "; ".join(
                        f"{x['name_primary']!r}/{x['name_second']!r}"
                        for x in flagged))
            else:
                # a terminal first: it is the one screen that proves itself,
                # since nothing else sets every character on one width, and
                # read as anything else it loses the split between what Jared
                # typed and what came back -- which is most of what it says
                term = console_reader.read_console(pane_path)
                if term.get("is_console"):
                    print(f"  [pane {pi}: a terminal]")
                    for line in console_reader.render(term).splitlines():
                        print("    " + line)
                    continue
                # not a tree: a column view before a document, since a table
                # read as prose loses the pairing of value to heading
                lst = columns.read_list(pane_path)
                if lst.get("is_list"):
                    print(f"  [pane {pi}: a list of columns]")
                    for line in columns.render(lst).splitlines():
                        print("    " + line)
                    continue
                # a live stream's chat log, before the document reader, which
                # would otherwise take it for prose and lose who said what
                chat = chat_reader.read_chat(pane_path)
                if chat.get("is_chat"):
                    print(f"  [pane {pi}: a chat log]")
                    for line in chat_reader.render(chat).splitlines():
                        print("    " + line)
                    continue
                # a document: the words AND the shape
                note = note_reader.read_note(pane_path)
                if note["markdown"].strip().count("\n") >= 3:
                    print(f"  [pane {pi}: an open document]")
                    for line in note["markdown"].splitlines():
                        print("    " + line)
                    continue
                res, _ = engine(pane_path)
                texts = [t for _, t, _ in (res or [])]
                if len(texts) < 4:
                    continue
                print(f"  [pane {pi}: text, not a tree]")
                print("    " + " | ".join(texts[:16]))
        print()


if __name__ == "__main__":
    main()
