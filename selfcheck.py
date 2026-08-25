"""Judge a drawn note against the rules the note is supposed to keep.

Every rule here was a fault first: something that shipped wrong, was caught
by eye, and must never need catching by eye again. The point is that a note
can be passed or failed by running this, so the next forty videos do not
each need a person to look at them.

    python3 selfcheck.py <note.md> [frames-dir]

With a frames directory it also checks the drawing against the real frames:
a camera drawn where there was none, or none drawn where the camera lay.
Exit code is the number of faults found, so a build can stop on it.
"""
import os
import re
import sys

BLOCK = re.compile(r'^<div class="sn-(?:stage|screen)"')
PCT = re.compile(r"(left|top|width|height):(-?[\d.]+)%")


def _pos(style):
    """left, top, width, height out of a slot's own style, in percents."""
    got = dict((k, float(v)) for k, v in PCT.findall(style))
    if len(got) < 4:
        return None
    return got["left"], got["top"], got["width"], got["height"]


def _boxes(block, cls):
    """Every box of one kind in a picture: (left, top, width, height, tag)."""
    out = []
    for m in re.finditer(r'<div class="([^"]*\b' + cls + r'\b[^"]*)" style="([^"]+)"', block):
        p = _pos(m.group(2))
        if p:
            out.append((p, m.group(1)))
    return out


def _overlap(a, b):
    """The share of box b that box a covers."""
    (al, at, aw, ah), (bl, bt, bw, bh) = a, b
    ix = max(0.0, min(al + aw, bl + bw) - max(al, bl))
    iy = max(0.0, min(at + ah, bt + bh) - max(at, bt))
    return (ix * iy) / max(1e-6, bw * bh)


def check(path, frames=None):
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    faults = []

    def bad(rule, where, what):
        faults.append((rule, where, what))

    # 1. a picture is never a photograph, and no camera picture is pasted in
    for k, ln in enumerate(lines, 1):
        if "data:image" in ln or "<img" in ln:
            bad("no pictures", f"line {k}", "an image was pasted into the note")
        if "<style" in ln or "<svg" in ln or "foreignObject" in ln:
            bad("obsidian strips it", f"line {k}",
                "a style or svg block, which Obsidian prints as text or drops")

    # 2. raw html renders only when the whole block is one line
    for k, ln in enumerate(lines, 1):
        if BLOCK.match(ln) and not ln.rstrip().endswith("</div>"):
            bad("one line per picture", f"line {k}",
                "a picture runs over several lines, so Obsidian shows the source")

    # 3. the desktop bar belongs in the pictures, not loose in the document
    for k, ln in enumerate(lines, 1):
        if "sn-menubar" in ln and "sn-screen" not in ln:
            bad("no loose menu bar", f"line {k}",
                "the desktop bar is repeated outside a screen picture")

    # 4. a window is not padded out with empty rows
    for k, ln in enumerate(lines, 1):
        runs = re.findall(r'(?:<tr class="sn-empty">.*?</tr>){7,}', ln)
        for r in runs:
            bad("no padding", f"line {k}",
                f"a window is padded with {r.count('sn-empty')} empty rows")

    # 5. the browser does not live inside another program's window
    for k, ln in enumerate(lines, 1):
        if "sn-screen" in ln:
            continue
        for m in re.finditer(r'<div class="sn-window sn-obsidian[^"]*".*?(?=<div class="sn-window|$)', ln):
            if "sn-tabs" in m.group(0) or "sn-urlbar" in m.group(0):
                bad("one window per card", f"line {k}",
                    "a browser strip is drawn inside the Obsidian window")

    # 5b. a path bar starts where every other path bar in the note starts:
    #     at the disk. One that starts elsewhere has a neighbouring window's
    #     words read into its row.
    bars = [re.sub(r"<[^>]+>", "", m.group(1))
            for m in re.finditer(r'<div class="sn-pathbar">(.*?)</div>', text)]
    roots = [b.split("›")[0].strip() for b in bars if b.strip()]
    if len(roots) >= 3:
        common = max(set(roots), key=roots.count)
        for k, ln in enumerate(lines, 1):
            for m in re.finditer(r'<div class="sn-pathbar">(.*?)</div>', ln):
                b = re.sub(r"<[^>]+>", "", m.group(1))
                if b.strip() and b.split("›")[0].strip() != common:
                    bad("a path starts at the disk", f"line {k}",
                        f"a path bar starts at {b.split(chr(8250))[0].strip()!r}, "
                        f"where the rest of the note starts at {common!r}")

    # every screen picture, one at a time
    pics = [(k, ln) for k, ln in enumerate(lines, 1) if BLOCK.match(ln)]
    if not pics:
        bad("a note has pictures", path, "no screen picture in the note at all")
    for k, ln in pics:
        stamp = re.search(r'class="sn-stamp">([^<]*)<', ln)
        when = stamp.group(1) if stamp else "?"
        slots = _boxes(ln, "sn-slot")
        ghosts = _boxes(ln, "sn-ghost")
        where = f"line {k} ({when})"

        # 6. every picture says which windows stood, and shows one of them
        if not slots and not ghosts:
            bad("a picture has windows", where, "the picture is empty")
        if not slots:
            bad("the front window is filled", where,
                "no window is drawn with its content; all are outlines")
        if not stamp:
            bad("stamped with its time", where, "the picture carries no timestamp")

        # 7. every outline says what it is
        for m in re.finditer(r'<div class="[^"]*sn-ghost[^"]*"[^>]*>(.*?)</div>', ln):
            if "sn-ghost-tag" not in m.group(1):
                bad("outlines are labelled", where, "an outline has no name on it")

        # 8. no window stands outside the screen it was on. Only a picture
        #    with the desktop bar in it holds the whole screen; without the
        #    bar the video was zoomed into a part of it, and a window
        #    running past the edge of the picture is what was really there.
        whole = "sn-deskbar" in ln
        for (p, cls) in slots + ghosts + _boxes(ln, "sn-camera"):
            l, t, w, h = p
            if w <= 0 or h <= 0 or l >= 100 or t >= 100 or l + w <= 0 or t + h <= 0:
                bad("a box you can see", where,
                    f"a box with nothing on the picture: left {l:.0f}% top {t:.0f}% "
                    f"width {w:.0f}% height {h:.0f}%")
            elif whole and (l < -0.5 or t < -0.5 or l + w > 100.5 or t + h > 100.5):
                bad("inside the screen", where,
                    f"the whole desktop is in view, yet a box runs off it: "
                    f"left {l:.0f}% top {t:.0f}% width {w:.0f}% height {h:.0f}%")

        # 9. an outline is drawn because the window was seen; a window the
        #    front window covers whole was not on the screen at all
        for (gp, _) in ghosts:
            for (sp, _) in slots:
                if _overlap(sp, gp) > 0.95:
                    bad("nothing swallows a window in view", where,
                        "an outline is drawn under a window that covered it whole")

        # 9b. one place, one window: two outlines of a like size over the same
        #     ground are one window drawn twice - its old place and its new
        #     one. A small outline inside a big one is a different thing: a
        #     window standing in front of another, which is what a browser's
        #     tab strip above a window looks like.
        for a in range(len(ghosts)):
            for b in range(len(ghosts)):
                if a == b:
                    continue
                aa = ghosts[a][0][2] * ghosts[a][0][3]
                bb = ghosts[b][0][2] * ghosts[b][0][3]
                like = min(aa, bb) / max(1e-6, max(aa, bb)) > 0.5
                if like and _overlap(ghosts[a][0], ghosts[b][0]) > 0.85:
                    bad("one outline per window", where,
                        "two outlines mark the same place, so one window is drawn twice")

        # 10. the desktop bar, when drawn, carries the bar's real words
        bar = re.search(r'<div class="sn-deskbar">(.*?)</div>\s*<div', ln)
        if bar and bar.group(1).count("<span") < 4:
            bad("the whole bar", where,
                "the desktop bar is drawn with only a word or two of its menu")

    # 11. against the record: every word the reader saw stands in some window,
    #     so a word read where the picture draws nothing means the picture is
    #     missing a window
    if frames and os.path.isdir(frames):
        recs = os.path.join(os.path.dirname(frames.rstrip("/")), "records.jsonl")
        if os.path.exists(recs):
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import json
            import draw2
            by_ts = {}
            for line in open(recs, encoding="utf-8"):
                r = json.loads(line)
                if r.get("ts"):
                    by_ts[r["ts"]] = r
            for k, ln in pics:
                st = re.search(r'class="sn-stamp">([\d:]+)(?: to ([\d:]+))?', ln)
                if not st:
                    continue
                lo, hi = st.group(1), st.group(2) or st.group(1)
                boxes = [p for (p, _) in _boxes(ln, "sn-slot") + _boxes(ln, "sn-ghost")
                         + _boxes(ln, "sn-camera")]
                if "sn-deskbar" in ln:
                    boxes.append((0.0, 0.0, 100.0, 3.0))   # the bar is drawn too
                if not boxes:
                    continue
                out_of, seen = 0, 0
                for ts, r in by_ts.items():
                    if not (lo <= ts <= hi):
                        continue
                    W, H = r.get("size") or [3840, 2160]
                    for p in r.get("panes") or []:
                        for it in draw2.items_of(p):
                            b = it["box"]
                            cx, cy = 100.0 * (b[0] + b[2]) / 2 / W, 100.0 * (b[1] + b[3]) / 2 / H
                            seen += 1
                            if not any(l - 1 <= cx <= l + w + 1 and t - 1 <= cy <= t + h + 1
                                       for (l, t, w, h) in boxes):
                                out_of += 1
                if seen >= 20 and out_of > 0.15 * seen:
                    bad("every word stands in a window", f"line {k} ({lo})",
                        f"{100 * out_of // seen}% of the words read were drawn "
                        f"on bare desktop, so a window is missing from the picture")

    # 12. against the frames themselves: the camera drawn where it really lay
    if frames and os.path.isdir(frames):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import shapes
        for k, ln in pics:
            stamp = re.search(r'class="sn-stamp">(\d\d:\d\d:\d\d)', ln)
            if not stamp:
                continue
            f = os.path.join(frames, stamp.group(1).replace(":", "-") + ".png")
            if not os.path.exists(f):
                continue
            real = shapes.camera_box(f)
            drawn = "sn-camera" in ln
            if real and not drawn:
                bad("the camera is outlined", f"line {k} ({stamp.group(1)})",
                    "the camera was on the screen and no outline says so")
            if drawn and not real:
                bad("the camera is outlined", f"line {k} ({stamp.group(1)})",
                    "an outline says camera where the frame has none")
    return faults


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    faults = check(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    if not faults:
        print("clean:", sys.argv[1])
        return 0
    seen = {}
    for rule, where, what in faults:
        seen.setdefault(rule, []).append((where, what))
    for rule, rows in seen.items():
        print(f"\n{rule} — {len(rows)}")
        for where, what in rows[:6]:
            print(f"   {where}: {what}")
        if len(rows) > 6:
            print(f"   ... and {len(rows) - 6} more")
    print(f"\n{len(faults)} faults")
    return min(len(faults), 120)


if __name__ == "__main__":
    sys.exit(main())
