#!/usr/bin/env python3
"""The STRUCTURAL gate: catch the faults the ink-overlap gate cannot.

    python3 verify_pictures.py <note.md> <frames-dir>

`compare.py` renders each picture and scores its ink against the frame. It
answers "does the ink land right", and it is blind to four things Tristan
found by eye that it passed anyway:

  - a whole window PRESENT in the frame but MISSING from the drawing, or
    drawn as an outline where it should be filled (a top-layer window),
  - a PLACEHOLDER label ("rest of the screen") left in a finished note,
  - a breadcrumb MANGLED into run-together text with its separators lost,
  - a DUPLICATED block of text.

This gate reads the note's own boxes and the frame's own windows (measured
by `shapes.windows`, the same ground truth the reader uses) and FAILS loudly
on each. It reports, per check, whether it could judge by machine. What it
cannot yet judge it says so out loud -- an unchecked thing declared unchecked
is honest; an unchecked thing counted as passed is the fault this exists to
stop.

Exit 1 if any picture fails a machine check, so a run can gate on it.
"""
import os
import re
import sys

import shapes


def pictures(note):
    """Each desktop picture: (stamp, heading, stage_html)."""
    heading = ""
    out = []
    for l in open(note, encoding="utf-8").read().split("\n"):
        if l.startswith("## ") or l.startswith("### "):
            heading = l.lstrip("# ").strip()
        if l.startswith('<div class="sn-stage">'):
            stamp = heading.split(" - ")[0].split(" to ")[0].strip()
            out.append((stamp, heading, l))
    return out


def boxes(stage, class_pat):
    """Every box of a class, as (left, top, right, bottom) in 0..1 of the
    screen, read from its percent style."""
    out = []
    for m in re.finditer(r'class="' + class_pat + r'" style="([^"]*)"', stage):
        st = dict(re.findall(r"(left|top|width|height):([\d.]+)%", m.group(1)))
        if len(st) == 4:
            l, t, w, h = (float(st[k]) / 100 for k in ("left", "top", "width", "height"))
            out.append((l, t, l + w, t + h))
    return out


def overlap(a, b):
    """Share of the SMALLER box the two share, 0..1."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    sa = (a[2] - a[0]) * (a[3] - a[1])
    sb = (b[2] - b[0]) * (b[3] - b[1])
    return inter / max(1e-9, min(sa, sb))


PLACEHOLDERS = ("rest of the screen", "a window behind", "its name unread",
                "some window", "unknown window")


def check_picture(stamp, stage, frame_path, fav_boxes=()):
    """Machine checks for one picture. Returns a list of failure strings.

    `fav_boxes` is the favorites-sidebar word boxes the reader read on this
    moment (empty when the records were not supplied); it drives the
    sidebar-completeness check, which is skipped without them."""
    fails = []
    filled = boxes(stage, r'sn-slot(?: sn-\w+)*')
    outline = boxes(stage, r'sn-ghost(?: sn-\w+)*')
    drawn = filled + outline

    # 1) EVERY WINDOW THE FRAME HAS IS IN THE DRAWING, and a TOP-LAYER window
    #    (one no other window covers) is FILLED, not merely outlined.
    if os.path.exists(frame_path):
        W, H = shapes._frame_size(frame_path)
        # A WINDOW IS SOMETHING A PERSON WORKS IN, AND THAT HAS A SIZE: the
        # reader's own law, a tenth of the screen. `shapes.windows` also
        # closes furniture -- a sidebar, a card, a pane inside a window --
        # and the drawer filters those out by this same law before it treats
        # a rectangle as a window to fill. The gate must hold the drawing to
        # the SAME definition, or it demands a filled box over every sidebar
        # and fails a picture that is right.
        least = 0.09 * W * H
        fw = [r for r in shapes.windows(frame_path)
              if (r[2] - r[0]) * (r[3] - r[1]) >= least]
        fboxes = [(o[0]/W, o[1]/H, o[2]/W, o[3]/H) for o in fw]
        top = [not any(j != i and overlap(fboxes[i], fboxes[j]) > 0.5
                       for j in range(len(fw)))
               for i in range(len(fw))]        # a window no other window covers

        def fills(d, i):
            """A filled box that fills window i and DOES NOT also swallow a
            different top-layer window. A single box drawn over the whole
            screen overlaps every window at once and would pass the plain
            test for each; it is one maximised fill masquerading as many, and
            the render that drew it left two side-by-side windows collapsed
            into one. Such a box fills NONE of them."""
            if overlap(fboxes[i], d) <= 0.5:
                return False
            for j in range(len(fw)):
                if j != i and top[j] and overlap(fboxes[j], d) > 0.5:
                    return False
            return True
        for i, r in enumerate(fw):
            box = fboxes[i]
            covered = not top[i]
            hit_any = any(overlap(box, d) > 0.5 for d in drawn)
            hit_filled = any(fills(d, i) for d in filled)
            where = "%.0f-%.0f%% across, %.0f-%.0f%% down" % (
                box[0]*100, box[2]*100, box[1]*100, box[3]*100)
            if not hit_any:
                fails.append("MISSING WINDOW: the frame has a window at %s with nothing drawn there" % where)
            elif not covered and not hit_filled:
                fails.append("WINDOW NOT FILLED: a top-layer window at %s is only outlined or swallowed by a screen-wide fill; a window nothing covers must be filled in its own right" % where)

    # 1b) A FILLED WINDOW SHOWED ITS SIDEBAR, SO THE PICTURE MUST TOO. The
    #     favorites sidebar (Recents, Shared, Applications, ...) is a Finder
    #     window's own furniture; the reader reads it, the window's card shows
    #     it, and a desktop-picture fill that drops it stretches the file list
    #     across the whole window -- the "missing window" a reader's eye sees.
    #     No plain window/fill check catches it, because the window IS drawn
    #     and IS filled; what is missing is content INSIDE the fill. So where
    #     the frame's own moment read a favorites sidebar (>= 2 of its fixed
    #     names), the drawing must put a sidebar down somewhere.
    if fav_boxes:
        if len(fav_boxes) >= 2 and 'sn-side' not in stage:
            fails.append("SIDEBAR DROPPED: the frame read a Finder favorites sidebar "
                         "(%d of Recents/Shared/Applications/...) but the picture draws none; "
                         "a filled window that showed its sidebar must draw it" % len(fav_boxes))

    # 2) NO PLACEHOLDER LABELS in a finished note.
    for tag in re.findall(r'sn-ghost-tag[^>]*>([^<]*)<', stage):
        if any(p in tag.lower() for p in PLACEHOLDERS):
            fails.append('PLACEHOLDER LABEL: "%s" is scaffolding, not a finished name' % tag)

    # 3) A BREADCRUMB IS SEGMENTED: crumbs separated, none run together.
    for pb in re.findall(r'<div class="sn-pathbar">(.*?)</div>', stage):
        crumbs = re.findall(r'<span>(?:<span[^>]*>[^<]*</span>)?([^<]+)</span>', pb)
        seps = pb.count('sn-sep')
        if len(crumbs) >= 2 and seps < len(crumbs) - 1:
            fails.append("BREADCRUMB RUN-TOGETHER: %d crumbs but %d separators" % (len(crumbs), seps))
        for c in crumbs:
            # a crumb that itself contains a run of a path is two crumbs glued
            if c.count(">") >= 1 or re.search(r"[a-z]{6,}-[A-Za-z]", c) or len(c) > 40:
                fails.append('BREADCRUMB CRUMB MANGLED: "%s"' % c.strip()[:50])
    return fails


def note_level(note):
    """Checks over the whole note, not one picture."""
    fails = []
    text = open(note, encoding="utf-8").read()
    # DUPLICATE Jared-quote blocks (the loose-ink duplication fault)
    quotes = re.findall(r"> \[!quote\][^\n]*\n> ([^\n]+)", text)
    seen = {}
    for q in quotes:
        k = q.strip()[:80]
        seen[k] = seen.get(k, 0) + 1
    for k, n in seen.items():
        if n > 1:
            fails.append('DUPLICATE QUOTE BLOCK (%dx): "%s..."' % (n, k[:50]))
    return fails


FAVORITES = ("recents", "shared", "applications", "pictures", "movies",
             "desktop", "documents", "downloads", "icloud")


def favorites_by_stamp(records):
    """For each moment, the favorites-sidebar word boxes the reader read, in
    0..1 frame fractions. The reader's WORDS, checked against the DRAWING --
    a completeness test, not geometry graded against its own geometry."""
    import draw as old
    import draw3
    hdr, moments, ftr = old.load(records)
    W, H = (moments[0].get("size") or [1, 1])[:2] if moments else (1, 1)
    out = {}
    for m in moments:
        favs = []
        for key, b in (draw3.word_boxes(m) or {}).items():
            k = key.replace(" ", "").lower()
            if any(f in k for f in FAVORITES):
                favs.append((b[0] / W, b[1] / H, b[2] / W, b[3] / H))
        out[m["ts"]] = favs
    return out


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    note, frames = sys.argv[1], sys.argv[2]
    records = sys.argv[3] if len(sys.argv) > 3 else None
    fav = favorites_by_stamp(records) if records else {}
    total = 0
    for stamp, heading, stage in pictures(note):
        frame = os.path.join(frames, stamp.replace(":", "-") + ".png")
        fails = check_picture(stamp, stage, frame, fav.get(stamp, ()))
        if fails:
            print("FAIL %s" % stamp)
            for f in fails:
                print("     " + f)
            total += len(fails)
    for f in note_level(note):
        print("FAIL note-level")
        print("     " + f)
        total += 1
    side_note = "" if fav else " (sidebar-completeness skipped: pass the records path as a 3rd arg to enable it)"
    print("\nMACHINE-CHECKED: window presence, top-layer fill, placeholder labels, breadcrumb segmentation, duplicate quote blocks, sidebar completeness%s." % side_note)
    print("NOT machine-checked (declared, not passed): relative type scale against the frame, and subjective legibility of rendered text. These need a rendered-pixel measure against the frame's own text heights; compare.py renders but does not yet measure type size.")
    if total:
        print("\n%d structural failure(s)." % total)
        return 1
    print("\nAll structural checks pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
