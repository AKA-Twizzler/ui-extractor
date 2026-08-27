#!/usr/bin/env python3
"""The STRUCTURAL gate: catch the faults the ink-overlap gate cannot.

    python3 verify_pictures.py <note.md> <frames-dir> [<records.jsonl>]

Pass the records as a third argument to enable the sidebar-completeness
check (a filled window that showed its favorites sidebar must draw it);
without them that one check is skipped and says so.

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

import bigwin
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


def _iou(a, b):
    """How much two boxes agree: shared area over the area they cover
    between them. Unlike `overlap`, a small box sitting inside a big one
    does NOT score high -- which is the whole point when the question is
    whether the drawing put a window where the screen had it, at the size
    the screen gave it."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter)
    return inter / max(1e-9, union)


AGREE = 0.5      # how much a drawn box and its window must agree


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
        fw = [r[:4] for r in shapes.windows(frame_path)
              if (r[2] - r[0]) * (r[3] - r[1]) >= least]
        # AND THE WINDOWS THE SCREEN CUTS OFF. `shapes` closes a window from
        # two sides plus a top and a foot, and offers the frame's edge as a
        # stand-in side but never as a stand-in FOOT -- so a window running
        # off the bottom of the screen is never measured, and a gate that
        # reads only `shapes` cannot fire on a window the reader never saw.
        # That blindness is why a picture missing the two LARGEST windows on
        # screen passed every gate; the browser and the Obsidian editor at
        # 00:00:00 are both this shape. `bigwin` measures them.
        for b in bigwin.big_windows(frame_path):
            if (b[2] - b[0]) * (b[3] - b[1]) >= least and not any(
                    _iou((b[0]/W, b[1]/H, b[2]/W, b[3]/H),
                         (r[0]/W, r[1]/H, r[2]/W, r[3]/H)) > 0.7 for r in fw):
                fw.append(tuple(b))
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

        # 1c) EVERY WINDOW ITS OWN BOX, AT ITS OWN SIZE. "Something is drawn
        #     over this window" is a weaker question than it sounds: overlap
        #     is scored against the SMALLER box, so a thin strip lying across
        #     a window answers yes for it, and one box lying across two
        #     windows answers yes for both. Measured on the delivered note:
        #     the browser stands 97% of the screen tall and is drawn as a 6%
        #     strip, and the check above passed it. So each measured window
        #     is matched to a box of its OWN -- best agreement first, each
        #     box spent once -- and that box has to be the window's size.
        order = sorted(((_iou(fboxes[i], d), i, j)
                        for i in range(len(fw)) for j, d in enumerate(drawn)),
                       reverse=True)
        took_w, took_d, best = set(), set(), {}
        for score, i, j in order:
            if i in took_w or j in took_d:
                continue
            took_w.add(i); took_d.add(j); best[i] = (score, drawn[j])
        for i in range(len(fw)):
            score, d = best.get(i, (0.0, None))
            if score >= AGREE:
                continue
            box = fboxes[i]
            where = "%.0f-%.0f%% across, %.0f-%.0f%% down" % (
                box[0]*100, box[2]*100, box[1]*100, box[3]*100)
            drawn_as = ("nothing of its own" if d is None else
                        "%.0f-%.0f%% across, %.0f-%.0f%% down" % (
                            d[0]*100, d[2]*100, d[1]*100, d[3]*100))
            fails.append("BOX OFF ITS WINDOW: the frame's window at %s has no box "
                         "of its own that agrees with it -- nearest is %s (%.2f)"
                         % (where, drawn_as, score))

    # 1b) A FILLED WINDOW SHOWED ITS SIDEBAR, SO THE PICTURE MUST TOO. The
    #     favorites sidebar (Recents, Shared, Applications, ...) is a Finder
    #     window's own furniture; the reader reads it, the window's card shows
    #     it, and a desktop-picture fill that drops it stretches the file list
    #     across the whole window -- the "missing window" a reader's eye sees.
    #     No plain window/fill check catches it, because the window IS drawn
    #     and IS filled; what is missing is content INSIDE the fill. So where
    #     the frame's own moment read a favorites sidebar (>= 2 of its fixed
    #     names), the drawing must put a sidebar down somewhere.
    if fav_boxes and 'sn-side' not in stage:
        # only a FILLED window owes a sidebar: favorites standing inside a
        # window that is drawn as an outline are a behind window's, and the
        # rule outlines those without content. So the sidebar is required
        # only where the favorites words sit inside a filled slot.
        def inside(pt, box):
            return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]
        for d in filled:
            n = sum(1 for f in fav_boxes
                    if inside(((f[0] + f[2]) / 2, (f[1] + f[3]) / 2), d))
            if n >= 2:
                fails.append("SIDEBAR DROPPED: a filled window at %.0f-%.0f%% across, "
                             "%.0f-%.0f%% down stands over %d favorites-sidebar names the "
                             "frame read, but the fill draws no sidebar" % (
                                 d[0]*100, d[2]*100, d[1]*100, d[3]*100, n))
                break

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


def _runs_of_text(html, least=40):
    """Every text run of some length drawn inside one picture."""
    out = []
    for t in re.findall(r">([^<>]+)<", html):
        t = " ".join(t.split())
        if len(t) >= least:
            out.append(t)
    return out


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
    # AND A DUPLICATED TEXT BLOCK IN A PICTURE, which is the same fault in
    # the form it actually took: a paragraph drawn twice inside ONE window.
    # The quote-callout test above cannot see it -- this note carries no
    # quote callouts at all, so that check has never once been able to fire,
    # and a check that cannot fire is protecting nothing. Across the note a
    # repeat is legitimate (the desktop picture and the window's own card
    # both show the same words); inside one picture it is not.
    for stamp, heading, stage in pictures(note):
        seen = {}
        for t in _runs_of_text(stage):
            seen[t] = seen.get(t, 0) + 1
        for t, n in seen.items():
            if n > 1:
                fails.append('DUPLICATE TEXT BLOCK at %s (%dx): "%s..."'
                             % (stamp, n, t[:50]))
    return fails


FAVORITES = ("recents", "shared", "applications", "pictures", "movies",
             "desktop", "documents", "downloads", "icloud")


def favorites_by_stamp(records):
    """For each moment, the favorites-sidebar word boxes the reader read, in
    0..1 frame fractions. The reader's WORDS, checked against the DRAWING --
    a completeness test, not geometry graded against its own geometry."""
    import draw as old
    import draw2
    import draw3
    hdr, moments, ftr = old.load(records)
    W, H = (moments[0].get("size") or [1, 1])[:2] if moments else (1, 1)
    out = {}
    for m in moments:
        favs = []
        for p in m.get("panes") or []:
            for it in draw2.items_of(p):
                k = draw3.fold(draw3.flat(it["text"])).replace(" ", "").lower()
                if len(k) >= 5 and any(f in k for f in FAVORITES):
                    b = it["box"]
                    favs.append((b[0] / W, b[1] / H, b[2] / W, b[3] / H))
        out[m["ts"]] = favs
    return out


# ---------------------------------------------------------------- proving

# A CHECK NEVER SEEN TO FAIL IS NOT A CHECK. Three times on this build a
# gate reported a fault that was its own bookkeeping, and twice a gate waved
# through the very thing it existed to catch -- a screen-wide box answering
# "filled" for every window at once. So every check here carries a crafted
# break beside it: a real picture from the note, damaged in exactly the way
# that check exists to catch, which the check must reject. `--prove` runs
# them all and says which checks have been seen to fail. A check that cannot
# be proved is reported as UNPROVED and is worth nothing until it is.


def _break_missing(stage):
    return re.sub(r'class="sn-(?:slot|ghost)', 'class="sn-was', stage)


def _break_unfilled(stage):
    return stage.replace('class="sn-slot', 'class="sn-ghost')


def _break_collapse(stage):
    return re.sub(r'(class="sn-slot[^"]*" style=")[^"]*"',
                  r'\1left:0.00%;top:0.00%;width:100.00%;height:100.00%"', stage)


def _break_placeholder(stage):
    return re.sub(r'(sn-ghost-tag[^>]*>)[^<]*<', r'\1rest of the screen<',
                  stage, count=1)


def _break_crumbs_glued(stage):
    def one(m):
        return '<div class="sn-pathbar">' + re.sub(
            r'<span class="sn-sep">[^<]*</span>', '', m.group(1)) + '</div>'
    return re.sub(r'<div class="sn-pathbar">(.*?)</div>', one, stage, count=1)


def _break_crumb_mangled(stage):
    return re.sub(r'(<div class="sn-pathbar"><span>(?:<span[^>]*>[^<]*</span>)?)[^<]+',
                  r'\1MacintoshHD>Users>jaredrhodenizer>.claude>projects', stage, count=1)


def _break_sidebar(stage):
    return stage.replace('sn-side', 'sn-wasside')


BREAKS = [
    ("window presence",        _break_missing,        "MISSING WINDOW"),
    ("top-layer fill",         _break_unfilled,       "WINDOW NOT FILLED"),
    ("maximised collapse",     _break_collapse,       "WINDOW NOT FILLED"),
    ("box agrees with window", _break_collapse,       "BOX OFF ITS WINDOW"),
    ("placeholder label",      _break_placeholder,    "PLACEHOLDER LABEL"),
    ("breadcrumb segmented",   _break_crumbs_glued,   "BREADCRUMB RUN-TOGETHER"),
    ("breadcrumb crumb whole", _break_crumb_mangled,  "BREADCRUMB CRUMB MANGLED"),
    ("sidebar completeness",   _break_sidebar,        "SIDEBAR DROPPED"),
]


def prove(note, frames, fav):
    """Each check, set against a picture broken exactly the way it guards."""
    pics = pictures(note)
    rows = []
    for name, brk, marker in BREAKS:
        state, why = "UNPROVED", "no picture in this note could carry the break"
        for stamp, heading, stage in pics:
            frame = os.path.join(frames, stamp.replace(":", "-") + ".png")
            if not os.path.exists(frame):
                continue
            favs = fav.get(stamp, ())
            base = check_picture(stamp, stage, frame, favs)
            if any(marker in f for f in base):
                continue                  # already failing: proves nothing
            broken = brk(stage)
            if broken == stage:
                continue                  # the break did not apply here
            got = check_picture(stamp, broken, frame, favs)
            if any(marker in f for f in got):
                state, why = "PROVED", "crafted at %s, rejected" % stamp
                break
            why = "crafted at %s and the check still passed it" % stamp
            state = "NOT PROVED"
        rows.append((name, state, why))

    # the note-level check, broken the same way: a paragraph drawn twice
    # inside one picture, which is the shape the duplication fault took.
    text = open(note, encoding="utf-8").read()
    m = None
    for stamp, heading, stage in pics:
        runs = _runs_of_text(stage)
        if runs:
            m = (stage, runs[0])
            break
    if m:
        stage, run = m
        doubled = text.replace(stage, stage.replace(
            ">" + run + "<", ">" + run + "<span>" + run + "</span><", 1), 1)
        tmp = note + ".prove-tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(doubled)
        try:
            hit = any("DUPLICATE" in f for f in note_level(tmp))
        finally:
            os.remove(tmp)
        rows.append(("no duplicated block", "PROVED" if hit else "NOT PROVED",
                     "a paragraph drawn twice in one picture, rejected" if hit
                     else "a paragraph drawn twice and the check passed it"))
    else:
        rows.append(("no duplicated block", "UNPROVED", "the note draws no text"))

    # THE GATE ITSELF: a run that examined nothing must not report a pass.
    # Measured: pointed at a note carrying no pictures at all, this gate
    # printed "All structural checks pass" -- the run-5 lesson that a
    # skipped stage is not a passing one, reappearing in the drawing gate.
    empty = note + ".prove-empty"
    with open(empty, "w", encoding="utf-8") as f:
        f.write("# a note with no pictures in it\n")
    try:
        hit = not pictures(empty)
    finally:
        os.remove(empty)
    rows.append(("a gate that saw nothing does not pass",
                 "PROVED" if hit else "NOT PROVED",
                 "a note with no pictures is refused" if hit
                 else "a note with no pictures was read as having some"))

    bad = 0
    for name, state, why in rows:
        print("%-9s %-38s %s" % (state, name, why))
        bad += state != "PROVED"
    print("\n%d of %d checks have been SEEN TO FAIL." % (len(rows) - bad, len(rows)))
    return 1 if bad else 0


def main():
    argv = [a for a in sys.argv[1:] if a != "--prove"]
    if len(argv) < 2:
        raise SystemExit(__doc__)
    note, frames = argv[0], argv[1]
    records = argv[2] if len(argv) > 2 else None
    fav = favorites_by_stamp(records) if records else {}
    if "--prove" in sys.argv:
        return prove(note, frames, fav)
    total = 0
    pics = pictures(note)
    # A GATE THAT EXAMINED NOTHING HAS NOT PASSED ANYTHING. Pointed at a
    # note carrying no pictures, this printed "All structural checks pass".
    if not pics:
        print("FAIL note-level\n     NO PICTURES: %s carries no desktop picture, "
              "so nothing here was checked at all" % os.path.basename(note))
        return 1
    for stamp, heading, stage in pics:
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
