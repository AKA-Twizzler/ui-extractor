#!/usr/bin/env python3
"""Point this at a video and get back what its interfaces show.

    python3 pipeline.py <video> [--every 10] [--limit 12]

It maps the video, captures one frame per distinct screen, and reads whatever
it can from each: the file tree where there is one, the text where there is
not. Everything it cannot settle is reported as unsettled rather than guessed.
"""
import os
import re
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

# What is drawn at twice a pane's own median glyph height is drawn LARGE,
# and the record says so -- size is layout, and a title is a title because
# of its size. Two sits in a measured gap: across 21 stored panes, body
# text, menus and table rows topped out at 1.5, slide titles reached 1.7 to
# 1.9, and the readings a person calls large without thinking -- a
# dashboard's dollar figures -- sat at 2.2 to 2.6, with nothing between
# 1.85 and 2.18. So a 1.8x slide title is deliberately not claimed: an
# under-claim, never a wrong one. Claimed only where the pane holds at
# least four readings to take a median of, and only for readings the other
# engine confirmed.
LARGE = 2.0


def guard(what, fn, *args, sink=None, **kwargs):
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
    return nothing. A caller assembling its output later passes `sink`, and
    the failure line lands in the record it belongs to instead of mid-stream.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as why:
        note = f"{what}: {type(why).__name__}: {why}"
        STUMBLED.append(note)
        line = f"[this reader fell over and the run went on -- {note}]"
        if sink is not None:
            sink.append(line)
        else:
            print("    " + line)
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


def say_pane(pane_path, pi, engine, drawn=(), camera=None):
    """Read one pane every way there is, and say what it turned out to be.

    Returns a record -- the pane's number, what it is, and its lines -- so
    compose() can put it under the window that holds it and name where it
    sits. None means nothing readable on it; the caller says so, once. The
    readings themselves are exactly what the readers rendered; assembly
    never rewrites a line, it only places it.

    `camera`, when given, takes the recogniser's boxes and answers which of
    them sit over moving video -- the webcam inset composited onto the screen.
    Only the loose-text fallback asks; a pane a real reader claims is read as
    what it is.
    """
    notes = []

    def record(kind, lines):
        return {"pi": pi, "kind": kind, "lines": lines, "notes": notes}

    def owned(lines):
        if not already_drawn(lines, drawn):
            return None
        return record("the text drawn on the picture, reported above", [])

    tree = guard(f"tree reader, pane {pi}", tree_reader.read_tree, pane_path,
                 sink=notes) or {}
    if tree.get("is_tree") and len(tree["rows"]) >= 5:
        got = owned([r["name"] for r in tree["rows"]])
        if got:
            return got
        tree = guard(f"second engine, pane {pi}",
                     verify_names.verify, pane_path, tree, sink=notes) or tree
        lines = tree_reader.render(tree).splitlines()
        flagged = [x for x in tree["rows"]
                   if x.get("name_status") not in ("confident", "reconciled")]
        if flagged:
            lines.append("  unsettled: " + "; ".join(
                f"{x.get('name_primary')!r}/{x.get('name_second')!r}"
                for x in flagged))
        return record("a file tree", lines)
    # a terminal first: it is the one screen that proves itself, since nothing
    # else sets every character on one width, and read as anything else it
    # loses the split between what Jared typed and what came back -- which is
    # most of what it says
    term = guard(f"terminal reader, pane {pi}",
                 console_reader.read_console, pane_path, sink=notes) or {}
    if term.get("is_console"):
        return record("a terminal", console_reader.render(term).splitlines())
    # not a tree: a column view before a document, since a table read as prose
    # loses the pairing of value to heading
    lst = guard(f"columns reader, pane {pi}", columns.read_list, pane_path,
                sink=notes) or {}
    if lst.get("is_list"):
        return record("a list of columns", columns.render(lst).splitlines())
    # a live stream's chat log, before the document reader, which would
    # otherwise take it for prose and lose who said what
    chat = guard(f"chat reader, pane {pi}",
                 chat_reader.read_chat, pane_path, engine=engine,
                 sink=notes) or {}
    if chat.get("is_chat"):
        return record("a chat log", chat_reader.render(chat).splitlines())
    # a document: the words AND the shape
    note = guard(f"document reader, pane {pi}",
                 note_reader.read_note, pane_path,
                 sink=notes) or {"markdown": "", "backed": 0}
    # lines of TEXT, not lines of output: the fences round a properties block
    # are structure the reader emits, so counting them lets two garbled words
    # come back as a document. And enough of those lines must be lines the
    # OTHER engine read too. Every line here is already read twice and
    # reconciled; nothing had ever looked at the verdict, so a stream's
    # leaderboard came back as prose -- "# 3 & Dr. Paris Woods", "a @& Alex
    # Palencia" -- with one line in eight backed.
    if (note_reader.body_lines(note["markdown"]) >= 3
            and note["backed"] >= note_reader.BACKED):
        got = owned(note["markdown"].splitlines())
        if got:
            return got
        return record("an open document", note["markdown"].splitlines())
    res, _ = engine(pane_path)
    texts = [t for _, t, _ in (res or [])]
    # each reading's own glyph height rides along, for the LARGE mark below
    heights = [max(p[1] for p in b) - min(p[1] for p in b)
               for b, _, _ in (res or [])]
    # Words over the webcam inset are not the screen's text -- the cap's
    # "Hat", the microphone's "fifine" -- and they used to enter the record
    # beside the real readings, marked unconfirmed but never placed. They are
    # split out and reported under their own truthful label, not dropped.
    video_words = []
    if camera and res:
        over = guard(f"camera zones, pane {pi}",
                     camera, [b for b, _, _ in res], sink=notes) or []
        video_words = [t for t, v in zip(texts, over) if v][:16]
        if video_words:
            texts = [t for t, v in zip(texts, over) if not v]
            heights = [h for h, v in zip(heights, over) if not v]
    # Nothing is dropped for being short. This used to skip any pane with
    # fewer than four readings, which is silent loss -- the worst kind,
    # because the output looks complete. On a slide of nine cards split into
    # three columns, the left column held three of them and was thrown away
    # without a word: "moonstone.co * 12k", "the tiny gem * 4k", "hearthstone
    # * 15k" simply were not in the answer. Whether a reading is worth
    # anything is what the confirmation below says, and it says it out loud.
    if not texts:
        if video_words:
            return record("only moving video on it",
                          ["[these sit over moving video] "
                           + " | ".join(video_words)])
        return None            # nothing on it; the caller says so, once
    got = owned(texts)
    if got:
        return got
    # nothing else placed this pane, so there is no structure to stand behind
    # the words. Printing them as read is how "R78" came off Jared's
    # visualizer -- three faint marks one engine calls R78 and the other calls
    # Ris. The rule this build runs on is that a string enters the record only
    # when the instruments confirm it, so say which ones did.
    marked = guard(f"confirmation, pane {pi}",
                   verify_names.confirm_readings, pane_path, texts[:16],
                   sink=notes)
    if marked is None:
        marked = [(t, False) for t in texts[:16]]
    # confirm_readings answers in input order, so heights still line up
    med = sorted(heights)[len(heights) // 2] if len(heights) >= 4 else 0
    big = [t for (t, ok), h in zip(marked, heights)
           if ok and med and h >= LARGE * med]
    sure = [t for (t, ok), h in zip(marked, heights)
            if ok and not (med and h >= LARGE * med)]
    doubt = [t for t, ok in marked if not ok]
    lines = []
    if big:
        lines.append("[drawn large] " + " | ".join(big))
    if sure:
        lines.append(" | ".join(sure))
    if doubt:
        lines.append("[only one engine read these] " + " | ".join(doubt))
    # "sit over" is the whole claim, chosen against the stronger wording. A
    # cap's lettering and a stream's chat line both stand over moving video;
    # only the first is not screen text, and the box cannot say which.
    if video_words:
        lines.append("[these sit over moving video] " + " | ".join(video_words))
    return record("text, not a tree", lines)


def where(box, W, H):
    """A place a person would say, from the rectangle alone.

    The words are deliberately coarse -- thirds of the screen each way, with
    "across" and "down" for what spans a side -- because the exact rectangle
    is printed beside them. The word is the courtesy; the numbers are the
    layout.
    """
    x0, y0, x1, y1 = box
    wide, tall = (x1 - x0) >= 0.85 * W, (y1 - y0) >= 0.85 * H
    if wide and tall:
        return "filling the screen"
    hw = ("left", "middle", "right")[min(2, int(3 * (x0 + x1) / 2 / W))]
    vw = ("top", "middle", "bottom")[min(2, int(3 * (y0 + y1) / 2 / H))]
    if wide:
        return "across the middle" if vw == "middle" else f"across the {vw}"
    if tall:
        return "down the middle" if hw == "middle" else f"down the {hw} side"
    if hw == vw == "middle":
        return "the middle of the screen"
    if vw == "middle":
        return f"the {hw}, midway down"
    return f"{vw} {hw}"


def where_in(box, win):
    """Where this pane sits inside its window, from the rectangles alone."""
    a, t, c, d = win
    ww, wh = max(1, c - a), max(1, d - t)
    x0, y0, x1, y1 = box
    if (x1 - x0) * (y1 - y0) >= 0.5 * ww * wh:
        return "its main body"
    hw = ("left", "middle", "right")[min(2, int(3 * ((x0 + x1) / 2 - a) / ww))]
    vw = ("top", "middle", "bottom")[min(2, int(3 * ((y0 + y1) / 2 - t) / wh))]
    if (x1 - x0) >= 0.85 * ww:
        return "across its middle" if vw == "middle" else f"across its {vw}"
    if (y1 - y0) >= 0.85 * wh:
        return "its middle band" if hw == "middle" else f"its {hw} side"
    if hw == vw == "middle":
        return "its middle"
    return f"its {hw}, midway" if vw == "middle" else f"its {vw} {hw}"


def iou(a, b):
    """How much of these two rectangles is the same rectangle."""
    ox = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    oy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ox * oy
    union = ((a[2] - a[0]) * (a[3] - a[1])
             + (b[2] - b[0]) * (b[3] - b[1]) - inter)
    return inter / union if union else 0.0


def top_text(img, win, engine, workdir, tag):
    """The words across a window's top strip, both engines agreeing.

    The strip is the height a title bar has at this frame's scale --
    measured, 2.6% of frame height matches it at 1080p (28px) and 4K (56px)
    alike. What is written there is often the window's title and sometimes
    its first line of content, and the strip cannot say which -- so the
    header claims only the geometry, "across its top", never that the words
    are a title. Only readings the other engine confirms enter the header;
    everything else still arrives through the panes with its own marks.
    """
    a, t, c, d = win
    sh = max(24, round(img.shape[0] * 0.026))
    strip = img[t:t + sh, a:c]
    if strip.size == 0:
        return []
    big = cv2.resize(strip, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    path = os.path.join(workdir, f"{tag}_top_{a}_{t}.png")
    cv2.imwrite(path, big)
    res, _ = engine(path)
    texts = [x for _, x, _ in (res or [])][:6]
    if not texts:
        return []
    marked = verify_names.confirm_readings(path, texts) or []
    return [x for x, ok in marked if ok]


def say_panel(panel):
    print("  [a panel drawn on the picture]")
    unsettled = set(panel.get("unsettled") or [])
    if panel["label"] and not unsettled:
        print(f"    {panel['label']}: {panel['value']}")
    else:
        for line in panel["lines"]:
            mark = "  <- only one engine read this" if line in unsettled else ""
            print(f"    {line}{mark}")


def unchanged_here(grey, prev, box):
    """Did this pane's pixels move at all since the last captured moment?

    The rule is zero pixels beyond compression noise, and the noise bound
    is the one already load-bearing in overlay.moving_zones: 8 grey levels.
    Measured on stacked captures one second apart, a still pane's largest
    pixel step was 3 and seven of eight panes had not one pixel over the
    bound; a pane with a webcam inset showed 2.6% of its pixels moving, and
    a desktop six seconds on carried 0.03%-0.9% -- a cursor's worth, which
    could as easily be a digit's worth, so ANY pixel over the bound means a
    full re-read. An under-claim costs the time we already spend; a
    tolerance is a bug waiting for its frame.
    """
    for pb, held in prev["boxes"].items():
        if same_rect(box, pb):
            x0, y0, x1, y1 = box
            a = grey[y0:y1, x0:x1]
            b = prev["grey"][y0:y1, x0:x1]
            if a.size and a.shape == b.shape \
                    and not (np.abs(a - b) > 8).any():
                return True, held
    return False, None


def say_record(rec, base, place):
    at = f" -- {place}" if place else ""
    if rec.get("since"):
        at += f" -- unchanged since {rec['since']}"
    print(f"{base}[pane {rec['pi']}: {rec['kind']}{at}]")
    for line in rec["lines"]:
        print(base + "  " + line)
    for line in rec["notes"]:
        print(base + "  " + line)


def same_rect(a, b, slack=4):
    """The same drawn rectangle, moment to moment.

    Measured: a stationary window's rect is IDENTICAL to the pixel one
    second apart (00:07:29 and 00:07:30 of the works video, twice over).
    The slack of four pixels covers the edge detector's wobble and nothing
    else -- the one drifting pair measured, a stream card re-drawn 11px
    off, is deliberately not the same rectangle. An under-claim, never a
    wrong one.
    """
    return all(abs(x - y) <= slack for x, y in zip(a, b))


def compose(records, wins, panels_found, img, engine, workdir, tag,
            memory=None):
    """Say the moment as the screen it was, not as a bag of numbered panes.

    Windows speak first, top to bottom, each pane under the window that
    holds it and named by where it sits; what belongs to no window follows,
    placed on the screen itself. Grouping and placement come from the
    rectangles alone -- a pane belongs to the window its centre sits in,
    which the library bears out: wherever the splitter cuts inside a drawn
    window, the pane lies wholly inside it, share 1.0, no straddlers.

    A floating panel that IS a found window -- the same rectangle, and
    panes were cut and read inside it -- is said once, as the window,
    marked drawn over the picture. Its raw dump mostly said the same words
    the structured readings say better, and the record must not carry both
    -- but not only: the Finder's own path bar lived in that dump and in no
    pane, so a dump line whose words the panes do not hold is kept, under
    its own label. A panel matching no read window keeps its whole block
    exactly as before.
    """
    H, W = img.shape[:2]
    owner = {}
    for rec in records:
        x0, y0, x1, y1 = rec["box"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for wi, (a, t, c, d) in enumerate(wins):
            if a <= cx < c and t <= cy < d:
                owner[rec["pi"]] = wi
                break
    over = {}
    for panel in panels_found:
        wi = next((wi for wi, win in enumerate(wins)
                   if iou(panel["box"], win) >= 0.7
                   and wi in owner.values()), None)
        if wi is None:
            say_panel(panel)
        else:
            over[wi] = panel
    for wi, win in sorted(enumerate(wins), key=lambda p: (p[1][1], p[1][0])):
        mine = [r for r in records if owner.get(r["pi"]) == wi]
        if not mine:
            continue
        head = (f"  [window -- {where(win, W, H)}, "
                f"{win[0]},{win[1]} to {win[2]},{win[3]}")
        if wi in over:
            head += " -- drawn over the moving picture"
        words = guard(f"top text in window {wi}", top_text, img, win, engine,
                      workdir, tag) or []
        if words:
            head += " -- across its top: " + " | ".join(words)
            if memory is not None:
                memory.append({"ts": tag.replace("-", ":"), "rect": win,
                               "where": where(win, W, H),
                               "words": " | ".join(words)})
        elif memory is not None:
            # this moment's strip would not confirm, but the SAME drawn
            # rectangle read earlier -- carry what it read, said as that
            known = [m for m in memory if same_rect(m["rect"], win)]
            if known:
                head += (f" -- its top read at {known[-1]['ts']}: "
                         + known[-1]["words"])
        print(head + "]")
        for rec in sorted(mine, key=lambda r: (r["box"][1], r["box"][0])):
            say_record(rec, "    ", where_in(rec["box"], win))
        panel = over.get(wi)
        if panel:
            # words of three letters and more, so an icon misread as "B" or
            # "Mi" neither keeps a line nor loses one
            body = verify_names._flat(" ".join(
                ln for r in mine for ln in r["lines"]))
            extra = [ln for ln in panel["lines"] if any(
                len(tok) >= 3 and tok.lower() not in body
                for tok in re.findall(r"[A-Za-z0-9]+", ln))]
            if extra:
                print("    [read across this window, not in any pane above]")
                unsettled = set(panel.get("unsettled") or [])
                for ln in extra:
                    mark = ("  <- only one engine read this"
                            if ln in unsettled else "")
                    print(f"      {ln}{mark}")
    loose = [r for r in records if r["pi"] not in owner]
    for rec in sorted(loose, key=lambda r: (r["box"][1], r["box"][0])):
        say_record(rec, "  ", where(rec["box"], W, H))
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
    # every window whose top strip both engines confirmed, moment by moment
    # -- the run's memory, for carrying words to a moment that cannot read
    # them, and for the index at the end
    seen_windows = []
    # the last captured moment's pixels and pane records, for reading only
    # what changed -- see unchanged_here for the rule and the measurements
    prev = None

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
        # owns that question and says why. The frame's drawn windows go along:
        # a panel inside a clearly larger window is the window's own furniture.
        # Panels are held back rather than printed here: whether one of them
        # is really a WINDOW this frame's panes were cut inside -- one thing,
        # to be said once -- is compose()'s question, and it cannot be
        # answered before the panes are read.
        wins = guard(f"windows at {ts}", overlay.windows, img) or []
        panels_found = list(overlay.floating(
            (guard(f"panel reader at {ts}", overlay.read_overlays,
                   path, engine) or {"panels": []})["panels"],
            regions, img.shape[1], screenness.WORK_WIDTH, wins))

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
            for panel in panels_found:
                say_panel(panel)
            print("    no readable interface at full size\n")
            continue

        # The webcam inset is the one part of a screen that is not the
        # screen. Where it is comes from the stretch -- overlay.moving_zones,
        # which says why and when it refuses -- computed once per frame and
        # only when a pane's loose text actually asks; most panes never do.
        # Text inside a drawn window is never the inset's, however it moved.
        #
        # And no zones at all on a moment the capture itself caught moving.
        # A recording that zooms or pans moves its SCREEN, so motion stops
        # meaning camera: on one zoomed-in Finder window the one readable
        # folder name came back labelled "over moving video". The zoomed
        # window's edges sit outside the frame, so no drawn window protects
        # its text either. When the screen was caught moving, nothing is
        # claimed -- a wrong label is worse than the unconfirmed mark those
        # words already carry.
        zone_state = {}

        def over_video(cx, cy, moving=("moving" in how)):
            if moving:
                return False
            if any(a <= cx < c and b <= cy < d for a, b, c, d in wins):
                return False
            if "z" not in zone_state:
                looks = overlay.frames_across(
                    video, secs, span=overlay.ZONE_SPAN,
                    looks=overlay.ZONE_LOOKS,
                    workdir=os.path.join(out_dir, "_zones"))
                got = guard(f"camera zones at {ts}",
                            overlay.moving_zones, looks)
                zone_state["z"] = got[0] if got else []
            return any(a <= cx < c and b <= cy < d
                       for a, b, c, d in zone_state["z"])

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
        quiet, unwritten, records = [], [], []
        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.int16)
        # reuse is only asked between two STACKED captures of the same-sized
        # frame: a moving capture's sharpest-frame picture carries motion
        # blur and real motion both, and pixel identity stops meaning
        # unchanged content
        can_reuse = (prev is not None and "moving" not in how
                     and "moving" not in prev["how"]
                     and grey.shape == prev["grey"].shape)
        cur_boxes = {}
        for pi, box in enumerate(guard(f"regions at {ts}", frame_regions,
                                       img, engine=engine) or []):
            box_t = tuple(int(v) for v in box)
            if can_reuse:
                still, held = unchanged_here(grey, prev, box_t)
                if still:
                    cur_boxes[box_t] = held
                    if held is None:
                        quiet.append(pi)
                    else:
                        rec = dict(held)
                        rec["pi"], rec["box"] = pi, box_t
                        rec["since"] = prev["ts"]
                        records.append(rec)
                    continue
            pane_path = os.path.join(
                out_dir, f"{ts.replace(':','-')}_pane{pi}.png")
            crop = write_box(img, box, pane_path)
            if crop is None:
                unwritten.append(pi)
                continue

            def camera(quads, box=box,
                       scale=crop.shape[1] / max(1, box[2] - box[0])):
                out = []
                for q in quads:
                    xs = [p[0] for p in q]
                    ys = [p[1] for p in q]
                    out.append(over_video(
                        box[0] + (min(xs) + max(xs)) / 2 / scale,
                        box[1] + (min(ys) + max(ys)) / 2 / scale))
                return out

            rec = say_pane(pane_path, pi, engine, drawn, camera)
            cur_boxes[box_t] = rec
            if rec is None:
                quiet.append(pi)
            else:
                rec["box"] = box_t
                records.append(rec)
        prev = {"ts": ts, "how": how, "grey": grey, "boxes": cur_boxes}
        # compose is guarded like any reader, but its failure may not cost
        # the readings it was handed -- they fall back to a flat, unplaced
        # list rather than out of the record.
        if guard(f"compose at {ts}", compose, records, wins, panels_found,
                 img, engine, out_dir, ts.replace(":", "-"),
                 memory=seen_windows) is None:
            for panel in panels_found:
                say_panel(panel)
            for rec in records:
                say_record(rec, "  ", "")
        if quiet:
            print(f"  [panes {', '.join(map(str, quiet))}: looked at, "
                  "nothing readable on them]")
        if unwritten:
            print(f"  [panes {', '.join(map(str, unwritten))}: too small to "
                  "cut out, not read]")
        print()

    if seen_windows:
        # the words each window carried across its top, collected once --
        # this is where a program's name reaches the record when the screen
        # wrote one anywhere, without a menu bar ever being readable
        print("[windows seen in this video]")
        said = set()
        for m in seen_windows:
            if m["words"] in said:
                continue
            said.add(m["words"])
            stamps = ", ".join(x["ts"] for x in seen_windows
                               if x["words"] == m["words"])
            print(f"   {m['words']} -- {m['where']}, at {stamps}")
        print()

    if STUMBLED:
        print(f"[{len(STUMBLED)} reader(s) fell over in this run and were "
              "stepped over]")
        for note in STUMBLED:
            print("   " + note)


if __name__ == "__main__":
    main()
