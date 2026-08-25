"""draw.py -- the note, drawn from the records.

    python draw.py <records.jsonl> [<note.md>]

The records file is what a run measured: one line per screen moment, each
carrying the exact text the run printed and the structures behind it --
every window's rectangle and top words, every pane's box, kind and reader
structure. This module turns that into the note a person opens: each window
on the screen drawn as its own section, on the vault's `screen-notes` style
sheet, with the words said under it, a map of where it sat, the fine print
of what stayed unsettled, and the moment-by-moment record folded at the end.

Nothing here reads the video. A changed shape changes this file and the
notes are redrawn from their records; the readers are untouched.
"""
import difflib
import html
import json
import os
import re
import sys


# ------------------------------------------------------------- the records

def entries(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load(path):
    header, moments, footer = None, [], None
    for e in entries(path):
        if e["kind"] == "header":
            header = e
        elif e["kind"] == "moment":
            moments.append(e)
        elif e["kind"] == "footer":
            footer = e
    return header or {}, moments, footer or {}


def diary(path):
    return "".join(e.get("text", "") for e in entries(path))


# ------------------------------------------------------------- small helpers

def esc(s):
    return html.escape(str(s), quote=False)


def same_rect(a, b, slack=4):
    return all(abs(int(x) - int(y)) <= slack for x, y in zip(a, b))


CLOCK = re.compile(r"^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s?[A-Z][a-z]{2}\s?\d{1,2}\s*)?"
                   r"(\d{1,2}:\d{2}\s?[AP]M)$")


def clock_in(pane):
    """The desktop clock, when a reading on this pane IS one.

    A time inside a file list's Date Modified column is not the clock; the
    clock is a reading on its own -- "FriJul3 9:19PM" -- with nothing else
    in it, so each reading is asked separately and a year disqualifies.
    """
    data = pane.get("data") or {}
    texts = [r.get("text") or "" for r in data.get("readings") or []]
    if not texts:
        texts = [w.strip() for ln in (pane.get("lines") or []) if not ln.startswith("[")
                 for w in ln.split(" | ")]
    for t in texts:
        m = CLOCK.match(t.strip())
        if m:
            return m.group(1)
    return None


def minutes(secs):
    secs = int(secs)
    if secs < 90:
        return f"{secs} seconds"
    return f"{secs // 60} minutes"


def pane_words(pane):
    """Every word a pane's record says, flat, for the app signatures."""
    return " ".join(pane.get("lines") or [])


# ------------------------------------------------------------- what a window is

def app_name(entry, panes):
    """The program, when the window's own contents say which.

    Nothing is guessed from a title alone: a Finder window shows the folder's
    name, not "Finder". What settles it is furniture only one program has --
    Finder's sidebar sections, Obsidian's properties panel beside a tree, a
    browser's address bar. With none of those the window is "a window", and
    its title, when read, names it.
    """
    words = " ".join(pane_words(p) for p in panes)
    kinds = {p["kind"] for p in panes}
    if any(w in words for w in ("Recents", "iCloud Drive", "AirDrop")) \
            and any(w in words for w in ("Favorites", "Locations", "Documents")):
        return "Finder"
    if "a file tree" in kinds and ("Properties" in words or "Add property" in words):
        return "Obsidian"
    if "Ask Google or type a URL" in words or "New Tab" in words:
        return "the browser"
    if "a terminal" in kinds:
        return "the terminal"
    if "a chat log" in kinds:
        return "the chat"
    return None


STRUCTURAL = ("an open document", "a file tree", "a list of columns", "a terminal", "a chat log")


def main_pane(panes):
    """The pane a window is about: a structured one with the most to say,
    else the biggest. The biggest alone was wrong on a desktop where the
    largest pane was a terminal's title strip read as loose words."""
    return max(panes, key=lambda p: (p["kind"] in STRUCTURAL, len(content_lines(p)),
                                     (p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1])))


def describe(panes):
    """What the main pane shows, in a few words: the note's first line,
    the tree's size and first row, the table's headings."""
    if not panes:
        return ""
    main = main_pane(panes)
    kind = main["kind"]
    lines = [ln.strip() for ln in content_lines(main) if ln.strip() and ln.strip() != "---"]
    if kind == "an open document":
        body = [re.split(r"\s+<- ", ln)[0] for ln in lines if not re.match(r"^[a-z_ ]+: ", ln)]
        body = [ln for ln in body if not is_bar(ln)]
        if main["box"][1] == 0 and len(body) > 1:
            body = body[1:]   # a pane touching the frame's top begins with the menu or title bar
        heads = [ln for ln in body if ln.startswith("#")]
        pick = heads[0] if heads else max(body[:6], key=lambda ln: len(ln.split()), default="")
        pick = pick.strip("#* ")
        return f"a note: {pick[:60]}" if pick else "a note"
    if kind == "a file tree":
        rows = (main.get("data") or {}).get("rows") or []
        first = (rows[0].get("name") if rows else "") or ""
        return f"a file tree, {len(rows)} rows, from {first[:30]}" if rows else "a file tree"
    if kind == "a list of columns":
        blocks = (main.get("data") or {}).get("blocks") or []
        head = " | ".join(blocks[0].get("header") or []) if blocks else ""
        return f"a table: {head[:60]}" if head else "a table"
    if kind == "a terminal":
        return "a terminal" + (f": {lines[-1][:50]}" if lines else "")
    if kind == "a chat log":
        return f"a chat log, {len(lines)} lines"
    words = " ".join(lines)[:60]
    return f"loose text: {words}" if words else "nothing readable"


def window_title(entry, panes):
    app = app_name(entry, panes)
    top = entry.get("top")
    if entry.get("screen"):
        return "The screen"
    if app and top:
        return f"The {app} window, titled {top}" if app != "Finder" else f"The Finder window, {top}"
    if app:
        return f"The {app} window"
    if top:
        return f"A window titled {top}"
    return "A window"


# ------------------------------------------------------------- the drawing

HUES = ("red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink")
SUFFIX = re.compile(r"\s+<- (.*)$")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![*\w])\*([^*\s][^*]*?)\*(?![*\w])")


def doc_line(line, fine):
    """One line of a read document, as HTML on the style sheet.

    The reader's markdown marks stay visible where markdown has them -- a
    heading's hashes, a bullet's dash -- and what markdown cannot say is a
    class on the style sheet. The reader's doubt suffixes ("<- the other
    engine read ...") leave the drawing for the fine print.
    """
    raw = line.rstrip()
    indent = len(raw) - len(raw.lstrip(" "))
    parts = re.split(r"\s+<- ", raw.strip())
    text = parts[0].strip()
    hue = None
    cut = False
    for note in parts[1:]:
        note = note.strip()
        if note.startswith("drawn in "):
            hue = note[len("drawn in "):].strip()
        elif note.startswith("the line runs on past the edge"):
            cut = True
            if ";" in note:
                fine.append(f"{text[:40]!r}… runs past the pane's edge; "
                            + note.split(";", 1)[1].strip())
        else:
            fine.append(f"{text[:40]!r}: {note}")
    if not text:
        return ""
    # A colour is measured for the WHOLE line, and a line is rarely coloured
    # whole: the ink the reader saw belonged to a few words inside it - a
    # code span, a link. Painting the line makes the drawing say something
    # the screen never said, so the colour is told in the fine print and the
    # line is drawn in the note's own ink.
    if hue in HUES:
        fine.append(f"{text[:40]!r}: something on this line was drawn in {hue}")
    cls = ""
    body = esc(text)
    body = BOLD.sub(r"<b>\1</b>", body)
    body = ITALIC.sub(r"<i>\1</i>", body)
    if cut:
        body += "…"
    if text == "---":
        return None                      # a properties fence, handled by the caller
    if is_bar(text):
        # a menu bar, a tab strip or an address bar read into the document:
        # clusters of words with wide gaps between, drawn as the strip it is
        clusters = [c.strip() for c in re.split(r"\s{4,}", text.lstrip("# ")) if c.strip()]
        return '<div class="sn-menubar">' + "".join(f"<span>{esc(c)}</span>" for c in clusters) + "</div>"
    m = re.match(r"(#{1,6}) (.*)", text)
    if m:
        level = min(3, len(m.group(1)))
        inner = esc(m.group(2))
        both = f"sn-h{level}"
        return f'<div class="{both}">{m.group(1)} {inner}</div>'
    pad = "&nbsp;" * min(12, indent)
    return f"<div{cls}>{pad}{body}</div>"


def is_bar(text):
    """Three or more word clusters with wide gaps between them on one line:
    a bar across the window, not a heading or a sentence."""
    clusters = [c for c in re.split(r"\s{4,}", text.strip().lstrip("# ")) if c.strip()]
    return len(clusters) >= 3


def content_lines(pane):
    """A structural pane's own lines: not the leftovers, not the doubt."""
    return [ln for ln in (pane.get("lines") or [])
            if not ln.strip().startswith(("[also on this pane", "unsettled:",
                                          "[dark look", "[light look"))]


def style_line(pane):
    """The pane's measured look, as the diary said it, for the fine print."""
    for ln in pane.get("lines") or []:
        if ln.strip().startswith(("[dark look", "[light look")):
            return fold_bands(ln.strip()[1:-1])
    return None


def fold_bands(text):
    """'a grey band under: X; a grey band under: Y; and 5 more banded rows'
    said once per colour: 'grey bands under 7 rows: X; Y'."""
    parts = [p.strip() for p in text.split("; ")]
    bands, rest, more = {}, [], 0
    for p in parts:
        m = re.match(r"an? (\w+) band under: (.*)$", p)
        if m:
            bands.setdefault(m.group(1), []).append(m.group(2))
            continue
        m = re.match(r"and (\d+) more banded rows?$", p)
        if m:
            more = int(m.group(1))
            continue
        rest.append(p)
    if not bands:
        return text
    said = []
    for hue, rows in bands.items():
        n = len(rows) + (more if hue == list(bands)[-1] else 0)
        more_note = f" and {more} more" if more and hue == list(bands)[-1] else ""
        if n == 1:
            said.append(f"a {hue} band under: {rows[0]}")
        else:
            said.append(f"{hue} bands under {n} rows: " + "; ".join(rows) + more_note)
    # the look comes first, then the bands, then the rest as said
    head = rest[:1] if rest and rest[0].endswith(" look") else []
    tail = rest[len(head):]
    return "; ".join(head + said + tail)


def draw_document(pane):
    lines = content_lines(pane)
    fine = []
    out = []
    props, in_props = [], False
    data = pane.get("data") or {}
    rows = data.get("rows") or []
    mono = (data.get("style") or {}).get("family") == "monospace"
    for line in lines:
        if line.strip() == "---":
            if in_props:
                out.append('<div class="sn-props"><b>Properties</b><br>'
                           + "<br>".join("☰ " + esc(p) for p in props) + "</div>")
                props = []
            in_props = not in_props
            continue
        if in_props:
            props.append(line.strip())
            continue
        h = doc_line(line, fine)
        if h:
            # the measured type on this line: leaning words, a rule under
            # it, a link's blue -- matched to the row the line came from
            row = next((r for r in rows if r.get("text") and r["text"][:30] in line), None)
            if row:
                if row.get("underline"):
                    h = h.replace("<div", "<div style=\"text-decoration:underline\"", 1)
                if row.get("link"):
                    h = h.replace("<div", "<div class=\"sn-link\"", 1)
                    fine.append(f"a link, blue: {row['text'][:40]!r}")
            out.append(h)
    cls = "sn-doc" + (" sn-tree" if mono else "")
    return f'<div class="{cls}">' + "".join(out) + picture_marks(data, pane.get("_skip_top")) + "</div>", fine


def draw_tree(pane):
    lines = content_lines(pane)
    fine = [ln.strip() for ln in (pane.get("lines") or [])
            if ln.strip().startswith("unsettled:")]
    rows = (pane.get("data") or {}).get("rows") or []
    banded = {r["name"] for r in rows if r.get("band")}
    out = []
    for ln in lines:
        h = esc(ln)
        if banded and any(ln.strip().endswith(n) for n in banded):
            hue = next(r["band"] for r in rows if r.get("band") and ln.strip().endswith(r["name"]))
            h = f'<span class="sn-{hue}" style="font-weight:600">{h}</span>'
            fine.append(f"the {hue} band: the tree row {ln.strip()!r} is drawn on it")
        out.append(h)
    return '<div class="sn-tree">' + "\n".join(out) + "</div>" + picture_marks(pane.get("data"), pane.get("_skip_top")), fine


def draw_list(pane):
    data = pane.get("data") or {}
    fine = []
    out = []
    for b in data.get("blocks") or []:
        head = b.get("header") or [f"col {i + 1}" for i in range(b.get("columns", 0))]
        rows = b.get("rows") or []
        out.append("<table>")
        out.append('<tr class="sn-head">' + "".join(f"<td>{esc(h)}</td>" for h in head) + "</tr>")
        flags = b.get("flags") or []
        styles = b.get("row_style") or []
        for ri, r in enumerate(rows):
            st = styles[ri] if ri < len(styles) else {}
            cls = ' class="sn-selected"' if st.get("band") else ""
            cells = [esc(c) for c in r]
            if st.get("icon") and cells:
                cells[0] = icon_span(st["icon"]) + cells[0]
            out.append(f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            if st.get("band"):
                fine.append(f"the {st['band']} band: the row {' | '.join(r)[:50]!r} is drawn on it")
            if ri < len(flags):
                for c, f in zip(r, flags[ri]):
                    if f:
                        fine.append(f"unsettled ({f}): {c!r}")
        out.append("</table>")
    if not out:
        # the lines are a markdown table already; keep them as read
        return '<div class="sn-body">' + "<br>".join(esc(ln) for ln in content_lines(pane)) + "</div>", fine
    return '<div class="sn-body">' + "".join(out) + picture_marks(data, pane.get("_skip_top")) + "</div>", fine


def draw_terminal(pane):
    lines = content_lines(pane)
    return '<div class="sn-tree">' + esc("\n".join(lines)) + "</div>", []


def draw_chat(pane):
    lines = content_lines(pane)
    return '<div class="sn-doc">' + "".join(f"<div>{esc(ln)}</div>" for ln in lines) + "</div>", []


def split_loose(pane):
    """A loose pane's lines, sorted into what is sure and what is doubt."""
    sure, doubt, video = [], [], []
    for ln in pane.get("lines") or []:
        s = ln.strip()
        if s.startswith("[only one engine read these]"):
            doubt.extend(x.strip() for x in s.split("]", 1)[1].split(" | "))
        elif s.startswith("[these sit over moving video]"):
            video.extend(x.strip() for x in s.split("]", 1)[1].split(" | "))
        elif s.startswith("[drawn large]"):
            sure.append(("large", s.split("]", 1)[1].strip()))
        elif s.startswith("[drawn in "):
            hue = s[len("[drawn in "):].split("]", 1)[0]
            sure.append((hue, s.split("]", 1)[1].strip()))
        elif s.startswith(("[dark look", "[light look")):
            continue          # the measured look; the data carries it, the drawing uses it
        elif s.startswith("["):
            doubt.append(s)
        else:
            sure.append((None, s))
    return sure, doubt, video


def draw_loose(pane, as_side=False):
    sure, doubt, video = split_loose(pane)
    fine = []
    if doubt:
        fine.append("only one engine read: " + " | ".join(doubt))
    if video:
        fine.append("over moving video: " + " | ".join(video))
    parts = []
    readings = (pane.get("data") or {}).get("readings") or []
    iconed = {r["text"].strip(): r["icon"] for r in readings if r.get("icon")}
    for mark, text in sure:
        items = [esc(x.strip()) for x in text.split(" | ") if x.strip()]
        if iconed:
            items = [(icon_span(iconed[x]) if x in iconed else "") + esc(x)
                     for x in (y.strip() for y in text.split(" | ")) if x]
        if mark == "large":
            items = [f'<span class="sn-title">{x}</span>' for x in items]
        elif mark in HUES:
            items = [f'<span class="sn-{mark}">{x}</span>' for x in items]
        parts.extend(items)
    pics = picture_marks(pane.get("data"))
    if not parts and not pics:
        return "", fine
    if as_side:
        # a sidebar whose items carry marks: an item without one, between
        # marked items, is a section label (Finder's Favorites, Locations)
        marked = sum(1 for x in parts if "sn-ico" in x)
        if marked >= 3 and marked >= len(parts) // 2:
            parts = [x if "sn-ico" in x else f'<div class="sn-section">{x}</div>' for x in parts]
            return '<div class="sn-side">' + "".join(
                x if x.startswith("<div") else x + "<br>" for x in parts) + pics + "</div>", fine
        return '<div class="sn-side">' + "<br>".join(parts) + pics + "</div>", fine
    return '<div class="sn-body">' + " &nbsp;·&nbsp; ".join(parts) + pics + "</div>", fine


def reading_order(items, box_of):
    """Items in reading order: rows top to bottom, left to right within a
    row. Two boxes share a row when their centres sit within half a box
    height of each other."""
    items = sorted(items, key=lambda it: ((box_of(it)[1] + box_of(it)[3]) / 2, box_of(it)[0]))
    rows, cur, cy = [], [], None
    for it in items:
        b = box_of(it)
        c = (b[1] + b[3]) / 2
        h = max(1, b[3] - b[1])
        if cy is not None and c - cy > 0.5 * h:
            rows.append(cur)
            cur = []
        cur.append(it)
        cy = c if cy is None or not cur[:-1] else cy
    if cur:
        rows.append(cur)
    out = []
    for row in rows:
        out.extend(sorted(row, key=lambda it: box_of(it)[0]))
    return out


def remainder_of(pane):
    """The readings a structural reader left out, by where they sat."""
    data = pane.get("data") or {}
    out = {"above": [], "below": [], "beside": [], "doubt": []}
    rem = data.get("remainder") or []
    if all(r.get("box") for r in rem):
        rem = reading_order(rem, lambda r: r["box"])
    for r in rem:
        if r.get("confirmed"):
            out[r.get("where") or "beside"].append(r["text"])
        else:
            out["doubt"].append(r["text"])
    return out


def draw_pane(pane):
    kind = pane["kind"]
    if kind == "an open document":
        return draw_document(pane)
    if kind == "a file tree":
        return draw_tree(pane)
    if kind == "a list of columns":
        return draw_list(pane)
    if kind == "a terminal":
        return draw_terminal(pane)
    if kind == "a chat log":
        return draw_chat(pane)
    return draw_loose(pane)


def toolbar(words, title=None, icons=0):
    spans = "".join(f'<span class="sn-btn">{esc(w)}</span>' for w in words)
    spans += "".join('<span class="sn-btn">▫</span>' for _ in range(min(icons, 8)))
    t = f"<b>{esc(title)}</b>" if title else ""
    return f'<div class="sn-toolbar"><span class="sn-lights"></span>{t}{spans}</div>'


def top_pictures(pane):
    """How many pictures sit along the top band of a pane: its toolbar's
    own buttons and icons, drawn as blank buttons."""
    data = pane.get("data") or {}
    pics = data.get("style", {}).get("pictures") or []
    if not pics:
        return 0, None
    # picture boxes are in the pane's own pixels, the same scale as its box
    h = max(1, pane["box"][3] - pane["box"][1])
    limit = max(48, int(0.12 * h))
    band = [p for p in pics if p["box"][1] < limit]
    return len(band), limit


def pathbar(words):
    return '<div class="sn-pathbar">' + "›".join(f"<span>{esc(w)}</span>" for w in words) + "</div>"


def draw_window(entry, panes, theme):
    """One window as the style sheet draws it: furniture, columns, content."""
    fine = []
    x0, y0, x1, y1 = entry["rect"]
    width = max(1, x1 - x0)
    panes = sorted(panes, key=lambda p: (p["box"][0], p["box"][1]))
    main = main_pane(panes)
    rest = remainder_of(main)
    # the furniture along the top: the window's own words across its top,
    # and what the main pane's reader found above its structure
    head = []
    top = entry.get("top")
    above = [w for w in rest["above"] if not top or w.strip() != top.strip()]
    n_icons, band_top = top_pictures(main)
    if top:
        head.append(toolbar(above, top, n_icons))
    elif above or n_icons:
        head.append(toolbar(above, None, n_icons))
    if above:
        fine.append("across the top, above the main pane's content: " + " | ".join(above))
    # columns: a narrow pane at the left is a sidebar; a tree beside a
    # document is the three-column shape
    side = [p for p in panes if p is not main and (p["box"][2] - p["box"][0]) < 0.36 * width
            and p["box"][0] <= x0 + 0.05 * width]
    cols = []
    if side:
        s = side[0]
        if s["kind"] == "a file tree":
            h, f = draw_tree(s)
        elif s["kind"] == "text, not a tree":
            h, f = draw_loose(s, as_side=True)
        else:
            h, f = draw_pane(s)
        fine.extend(f)
        cols.append(h)
        sr = remainder_of(s)
        for where in ("above", "beside", "below"):
            if sr[where]:
                fine.append(f"also on the side pane, {where}: " + " | ".join(sr[where]))
        if sr["doubt"]:
            fine.append("side pane, only one engine read: " + " | ".join(sr["doubt"]))
    drawn_main = dict(main, _skip_top=band_top) if band_top else main
    h, f = draw_pane(drawn_main)
    fine.extend(f)
    cols.append(h)
    others = [p for p in panes if p is not main and p not in side]
    height = max(1, y1 - y0)
    tabs, below, foot_words = [], [], []
    for p in others:
        pr = remainder_of(p)
        for where in ("above", "beside", "below"):
            if pr[where]:
                fine.append(f"also on the {p.get('where_in') or 'pane'}, {where}: " + " | ".join(pr[where]))
        if pr["doubt"]:
            fine.append("only one engine read: " + " | ".join(pr["doubt"]))
        if p["kind"] == "text, not a tree":
            sure, doubt, video = split_loose(p)
            if doubt:
                fine.append(f"{p.get('where_in') or 'a pane'}, only one engine read: " + " | ".join(doubt))
            if video:
                fine.append(f"{p.get('where_in') or 'a pane'}, over moving video: " + " | ".join(video))
            words = [w.strip() for _, t in sure for w in t.split(" | ") if w.strip()]
            if not words:
                continue
            # a strip of words along the window's top is its tab strip or
            # toolbar; along its bottom, a status line; anything else is
            # content and stacks under the columns
            if p["box"][1] < y0 + 0.08 * height and (p["box"][3] - p["box"][1]) < 0.2 * height:
                tabs.extend(words)
                continue
            if p["box"][3] > y1 - 0.06 * height and (p["box"][3] - p["box"][1]) < 0.12 * height:
                foot_words.extend(words)
                continue
        h, f = draw_pane(p)
        if p["kind"] != "text, not a tree":
            fine.extend(f)  # a loose pane's doubts were said above, with their place
        below.append(h)
    if rest["beside"]:
        fine.append("also on the main pane, beside its content: " + " | ".join(rest["beside"]))
    if rest["doubt"]:
        fine.append("main pane, only one engine read: " + " | ".join(rest["doubt"]))
    if tabs:
        head.insert(0, '<div class="sn-tabs">' + "".join(f'<span class="sn-tab">{esc(w)}</span>' for w in tabs) + "</div>")
    body = "".join(cols)
    if len(cols) >= 2:
        wide = side and (side[0]["box"][2] - side[0]["box"][0]) > 0.22 * width
        cls = "sn-cols sn-wide-left" if wide else "sn-cols"
        body = f'<div class="{cls}">{body}</div>'
    body += "".join(below)
    foot = ""
    if foot_words:
        foot = '<div class="sn-pathbar">' + " &nbsp;·&nbsp; ".join(esc(w) for w in foot_words) + "</div>"
    if rest["below"]:
        # a path's crumbs are names: no space, or one space after a capital,
        # never an apostrophe. A sentence below the list is the window
        # behind showing through, and stays as words, not a path
        crumbs, words = [], []
        for w in rest["below"]:
            c = w.rstrip(">").strip()
            name_like = (len(c) <= 28 and "'" not in c and
                         (" " not in c or (c.count(" ") == 1 and c[:1].isupper())))
            (crumbs if name_like else words).append(c)
        marked = any("›" in w or w.endswith(">") for w in rest["below"])
        if crumbs and (marked or len(crumbs) >= 3):
            foot += pathbar(crumbs)
        else:
            words = crumbs + words
        if words:
            foot += '<div class="sn-pathbar">' + " &nbsp;·&nbsp; ".join(esc(w) for w in words) + "</div>"
    cls = "sn-window sn-dark" if theme == "dark" else "sn-window"
    # a doubt reaches the fine print by two roads (the leftover record and
    # the pane's own line); say each payload once, under its first label
    seen, once = set(), []
    for f in fine:
        payload = f.split(": ", 1)[1] if ": " in f else f
        label = "doubt" if "only one engine read" in f else "video" if "over moving video" in f else None
        key = (label, payload) if label else f
        if key in seen:
            continue
        seen.add(key)
        once.append(f)
    return f'<div class="{cls}">{"".join(head)}{body}{foot}</div>', once


def draw_map(size, rect, share, label, pointer=None):
    W, H = size or (1920, 1080)
    sx, sy = 384 / W, 216 / H
    x0, y0, x1, y1 = rect
    win = (f'<rect class="win" x="{x0 * sx:.0f}" y="{y0 * sy:.0f}" '
           f'width="{(x1 - x0) * sx:.0f}" height="{(y1 - y0) * sy:.0f}"/>'
           f'<text x="{x0 * sx + 5:.0f}" y="{y0 * sy + 13:.0f}">{esc(label)}</text>')
    if pointer:
        px, py = pointer["box"][0] * sx, pointer["box"][1] * sy
        win += (f'<circle cx="{px:.0f}" cy="{py:.0f}" r="3" fill="#d33a3a"/>'
                f'<text class="muted" x="{px + 5:.0f}" y="{py + 4:.0f}" font-size="9">pointer</text>')
    tag = f'<text class="muted" x="290" y="208" font-size="9">screen {share:.0f}%</text>' if share else ""
    return ('<div class="sn-map"><svg viewBox="0 0 384 216" xmlns="http://www.w3.org/2000/svg">'
            '<rect class="frame" x="0.5" y="0.5" width="383" height="215"/>'
            f'{win}{tag}</svg></div>')


# ------------------------------------------------------------- the states

def is_menubar(pane, H):
    """A strip along the very top of the frame: the menu bar and the clock."""
    if not H:
        return False
    x0, y0, x1, y1 = pane["box"]
    return y0 < 0.02 * H and y1 < 0.07 * H


def window_key(rect, seen):
    """The same drawn rectangle across moments is the same window."""
    for k, r in seen.items():
        if same_rect(r, rect, slack=12):
            return k
    k = len(seen)
    seen[k] = rect
    return k


def signature(panes):
    return tuple((p["kind"], tuple(p.get("lines") or [])) for p in
                 sorted(panes, key=lambda p: p["pi"]))


SAME_SCREEN = 0.9   # character-level likeness at which two readings are one screen


def flat_text(panes):
    return re.sub(r"[^a-z0-9]", "", " ".join(
        ln for p in sorted(panes, key=lambda p: p["pi"]) for ln in content_lines(p)).lower())


def likeness(a, b):
    """How alike two states' readings are, by their letters.

    Exact lines cannot say it: the same file grid read seven times in a
    row shares only 0.63 to 0.68 of its lines, a third of them wobbling by
    a letter, and it was drawn seven times. By letters those repeats score
    0.93 to 0.97 and a real change 0.78 or under (measured on two videos).
    """
    A, B = flat_text(a), flat_text(b)
    if not A or not B:
        return 0.0
    return difflib.SequenceMatcher(None, A, B, autojunk=False).ratio()


def pane_rows(pane):
    """The row names of a tree or list, for stitching a scrolled view."""
    if pane["kind"] == "a file tree":
        return [r.get("name") for r in (pane.get("data") or {}).get("rows") or []]
    if pane["kind"] == "a list of columns":
        return [tuple(r) for b in (pane.get("data") or {}).get("blocks") or []
                for r in b.get("rows") or []]
    return None


def overlap(a, b):
    """How many rows at the end of a reappear at the start of b."""
    best = 0
    for n in range(min(len(a), len(b)), 2, -1):
        if a[-n:] == b[:n]:
            return n
    return best


def states(moments):
    """The windows across the video, each as a run of states.

    A state is one window showing one thing. Consecutive moments where the
    window's panes read the same are one state with several times. A
    scrolled tree or list -- the rows at the end of one moment at the start
    of the next -- is one state, stitched. A window that returns to a
    state it was in before is said once, pointing back.
    """
    seen = {}
    out = []                 # [{"key", "entry", "panes", "times", "moments", "stitched"}]
    for m in moments:
        by_wi = {}
        for p in m.get("panes") or []:
            if p.get("wi") is not None:
                by_wi.setdefault(p["wi"], []).append(p)
        windows = list(m.get("windows") or [])
        # panes in no found window: when the interface fills the frame no
        # window edge is found, and the panes are the screen itself. They
        # are drawn as one screen, on the frame's own rectangle; the menu
        # bar strip along the top stays with the desktop
        W, H = m.get("size") or (0, 0)
        lone = [p for p in m.get("panes") or []
                if p.get("wi") is None and not is_menubar(p, H)]
        around = []
        if lone and not any(by_wi.get(e["wi"]) for e in windows):
            windows.append({"wi": "screen", "rect": [0, 0, W, H],
                            "where": "filling the screen", "top": None,
                            "top_from": None, "drawn_over": False,
                            "newly": [], "panel_extra": [], "screen": True})
            by_wi["screen"] = lone
        else:
            around = lone
        for entry in windows:
            panes = by_wi.get(entry["wi"]) or []
            if not panes:
                continue
            key = window_key(entry["rect"], seen)
            sig = signature(panes)
            last = next((s for s in reversed(out) if s["key"] == key), None)
            if last is not None and last is out[-1] and last["sig"] == sig:
                last["times"].append(m["ts"])
                last["moments"].append(m)
                continue
            if last is not None and last is out[-1]:
                stitched = stitch(last, panes)
                if stitched:
                    last["times"].append(m["ts"])
                    last["moments"].append(m)
                    last["stitched"] = True
                    last["sig"] = sig
                    continue
                if likeness(last["panes"], panes) >= SAME_SCREEN:
                    # the same screen read again: one state, the fullest
                    # reading drawn, the others' differences counted
                    before = set(ln for p in last["panes"] for ln in content_lines(p))
                    now = set(ln for p in panes for ln in content_lines(p))
                    last["times"].append(m["ts"])
                    last["moments"].append(m)
                    # a line a letter off its twin is a wobble; one with no
                    # near twin at all was read differently
                    wob = diff = 0
                    for ln in now - before:
                        best = max((difflib.SequenceMatcher(None, ln, b).ratio() for b in before), default=0)
                        if best >= 0.8:
                            wob += 1
                        else:
                            diff += 1
                    last.setdefault("wobble", []).append((m["ts"], wob, diff))
                    if sum(len(content_lines(p)) for p in panes) > sum(
                            len(content_lines(p)) for p in last["panes"]):
                        last["panes"], last["sig"] = panes, sig
                    continue
            again = next((s for s in out if s["key"] == key and s["sig"] == sig), None)
            out.append({"key": key, "entry": entry, "panes": panes, "sig": sig,
                        "times": [m["ts"]], "moments": [m], "stitched": False,
                        "again": again, "size": m.get("size"), "share": m.get("share"),
                        "around": around})
    return out


def stitch(state, panes):
    """Join a scrolled view onto the state it continues; True when it did."""
    mine = {p["pi"]: p for p in state["panes"]}
    theirs = {p["pi"]: p for p in panes}
    if set(mine) != set(theirs):
        return False
    joined = {}
    for pi, p in theirs.items():
        q = mine[pi]
        if p["kind"] != q["kind"]:
            return False
        a, b = pane_rows(q), pane_rows(p)
        if a is None:
            if (p.get("lines") or []) != (q.get("lines") or []):
                return False
            continue
        n = overlap(a, b)
        if n == 0 and a != b:
            return False
        if n and a != b:
            joined[pi] = n
    if not joined:
        return False
    for pi, n in joined.items():
        q, p = mine[pi], theirs[pi]
        if p["kind"] == "a file tree":
            q["data"]["rows"] = q["data"]["rows"] + p["data"]["rows"][n:]
            body = [ln for ln in p["lines"] if ln.strip() and not ln.strip().startswith(("unsettled", "[also"))]
            q["lines"] = [ln for ln in q["lines"] if not ln.strip().startswith(("unsettled", "[also"))] + body[n:]
        else:
            blocks = q["data"]["blocks"]
            blocks[-1]["rows"] = blocks[-1]["rows"] + [list(r) for r in pane_rows(p)[n:]]
    return True


# ------------------------------------------------------------- the note

def said_block(moments):
    out = []
    for m in moments:
        said = (m.get("said") or "").strip()
        if not said:
            continue
        if len(said) > 700:
            words = len(said.split())
            out.append(f'> [!quote]- Jared, {m["ts"]} ({words} words)\n> ' + esc(said).replace("\n", "\n> "))
        else:
            out.append(f'Jared, {m["ts"]}: "{esc(said)}"')
    return "\n\n".join(out)


def desktop_section(moments, sts=()):
    """What sat on no window: the menu bar, the clock, loose readings."""
    menubar, clocks, loose = [], [], []
    drawn = {id(p) for s in sts for p in s["panes"]}
    for m in moments:
        H = (m.get("size") or [0, 0])[1]
        lone = [p for p in m.get("panes") or [] if p.get("wi") is None]
        strips = [p for p in lone if is_menubar(p, H)]
        others = [p for p in lone if p not in strips]
        for p in lone:
            c = clock_in(p)
            if c and (not clocks or clocks[-1][1] != c):
                clocks.append((m["ts"], c))
        for p in strips:
            sure, doubt, video = split_loose(p) if p["kind"] == "text, not a tree" else ([], [], [])
            words = [w for _, t in sure for w in t.split(" | ") if not CLOCK.match(w.strip())]
            menubar.extend(w for w in words if w not in menubar)
        # a lone pane that is not part of a screen-state (one loose pane
        # on its own) is said here; the rest were drawn as the screen
        if (len(others) == 1 and others[0]["kind"] == "text, not a tree"
                and id(others[0]) not in drawn):
            loose.append((m["ts"], others[0]))
    parts = ["## The desktop"]
    if menubar or clocks:
        right = f"{clocks[0][1]} at the start, {clocks[-1][1]} at the end" if len(clocks) > 1 else (clocks[0][1] if clocks else "")
        parts.append(f'<div class="sn-menubar"><span>{" &nbsp; ".join(esc(w) for w in menubar)}</span><span>{esc(right)}</span></div>')
    if clocks:
        parts.append('<span class="sn-fine">the desktop clock: ' + "; ".join(f"{c} at {ts}" for ts, c in clocks) + "</span>")
    seen = set()
    for ts, p in loose:
        sig = (p["kind"], tuple(p.get("lines") or []))
        if sig in seen:
            continue
        seen.add(sig)
        h, f = draw_pane(p)
        sure, _, _ = split_loose(p)
        if sure:
            parts.append(f'**{p.get("where") or "on the screen"}, {ts}**\n\n<div class="sn-window">{h}</div>')
        if f:
            parts.append('<span class="sn-fine">' + esc(f"{p.get('where') or 'on the screen'}, {ts}: " + "; ".join(f)) + "</span>")
    return "\n\n".join(parts) if len(parts) > 1 else ""


def events(moments, sts):
    """The order of events: one line per moment, what was on screen."""
    lines = []
    for m in moments:
        what = []
        for s in sts:
            if m in s["moments"] and s["moments"][0] is m:
                name = window_title(s["entry"], s["panes"])
                name = (name[0].lower() + name[1:]) if name.startswith(("The ", "A ")) else name
                what.append(f"{name}: {describe(s['panes'])}")
        newly = [w for e in m.get("windows") or [] for w in (e.get("newly") or [])]
        bit = "; ".join(what) or "the same screen"
        if newly:
            bit += " -- newly readable: " + " | ".join(newly[:8]) + (f" and {len(newly) - 8} more" if len(newly) > 8 else "")
        how = m.get("how") or ""
        if how and "unchanged" in how:
            bit += " (unchanged)"
        lines.append((m["ts"], bit))
    # a run of "the same screen" folds into one line naming its span
    out, i = [], 0
    while i < len(lines):
        ts, bit = lines[i]
        if bit == "the same screen":
            j = i
            while j + 1 < len(lines) and lines[j + 1][1] == "the same screen":
                j += 1
            if j > i:
                out.append(f"- {ts} to {lines[j][0]} - the same screen, read {j - i + 1} times")
                i = j + 1
                continue
        out.append(f"- {ts} - {bit}")
        i += 1
    return "\n".join(out)


def theme_of(panes):
    """Dark or light, from the measured look of the window's panes."""
    votes = {}
    for p in panes:
        d = p.get("data") or {}
        t = ((d.get("style") or {}).get("look") or {}).get("theme") or d.get("theme")
        if t:
            votes[t] = votes.get(t, 0) + 1
    return max(votes, key=votes.get) if votes else None


def picture_marks(data, skip_top=None):
    """Placeholders for the pictures a pane held where no text was.

    `skip_top` leaves out the pictures along the pane's top band, which
    the window draws in its toolbar instead."""
    pics = (data or {}).get("style", {}).get("pictures") or []
    if skip_top:
        pics = [p for p in pics if p["box"][1] >= skip_top]
    out = []
    for p in pics[:4]:
        x0, y0, x1, y1 = p["box"]
        out.append(f'<span class="sn-picture">picture {x1 - x0}×{y1 - y0}'
                   + (f", {p['hue']}" if p.get("hue") not in (None, "black", "white", "grey") else "")
                   + "</span>")
    return " ".join(out)


def icon_span(hue):
    cls = "sn-ico" if hue in ("green",) else ("sn-ico file" if hue == "white" else "sn-ico grey")
    return f'<span class="{cls}"></span>'


def note(records_path, diary_text=None):
    header, moments, footer = load(records_path)
    title = header.get("title") or os.path.basename(os.path.dirname(records_path))
    sts = states(moments)
    diary_text = diary_text if diary_text is not None else diary(records_path)
    secs = (moments[-1]["secs"] - moments[0]["secs"]) if len(moments) > 1 else 0
    apps = []
    for s in sts:
        app = app_name(s["entry"], s["panes"])
        name = (f"{app[0].upper() + app[1:]}" if app else None) or window_title(s["entry"], s["panes"])
        if name not in apps and name.lower() not in ("the screen", "a window"):
            apps.append(name)
    clocks = [c for m in moments for p in m.get("panes") or [] for c in [clock_in(p)] if c]
    parts = []
    # no frontmatter here: the master note lives beside the video's images,
    # and vault_sync adds the vault's own when it copies the note in
    parts.append(f"# {title}\n")
    head = (f"A screen recording, {minutes(secs)} read, {len(moments)} screen moments"
            + (" in order" if header.get("dense") else "") + ".")
    if apps:
        head += " On screen: " + "; ".join(
            (a[0].lower() + a[1:]) if a.startswith(("The ", "A ")) else a for a in apps) + "."
    if clocks:
        head += f" The desktop clock read {clocks[0]}" + (f" at the start and {clocks[-1]} at the end." if clocks[-1] != clocks[0] else ".")
    parts.append(head + "\n")
    parts.append("**The order of events**\n\n" + events(moments, sts) + "\n\n---\n")
    for s in sts:
        name = window_title(s["entry"], s["panes"])
        times = s["times"]
        when = times[0] if len(times) == 1 else (f"{times[0]} to {times[-1]}" if len(times) > 2 else f"{times[0]} and {times[1]}")
        if s["again"]:
            parts.append(f"## {name} - as at {when}, the same as at {s['again']['times'][0]}\n")
            said = said_block(s["moments"])
            if said:
                parts.append(said + "\n")
            parts.append("---\n")
            continue
        parts.append(f"## {name} - as at {when}" + (", scrolled" if s["stitched"] else "")
                     + f" - {describe(s['panes'])}\n")
        pointer = s["moments"][0].get("pointer")
        parts.append(draw_map(s["size"], s["entry"]["rect"], s["share"] or 0,
                              app_name(s["entry"], s["panes"]) or "window", pointer) + "\n")
        theme = theme_of(s["panes"])
        h, fine = draw_window(s["entry"], s["panes"], theme)
        parts.append(h + "\n")
        said = said_block(s["moments"])
        if said:
            parts.append(said + "\n")
        around = []
        for p in s.get("around") or []:
            sure, doubt, video = split_loose(p) if p["kind"] == "text, not a tree" else ([], [], [])
            if p["kind"] != "text, not a tree":
                around.append(f"{p.get('where') or 'on the screen'}: {p['kind']}: "
                              + " | ".join(content_lines(p))[:400])
            elif sure:
                around.append(f"{p.get('where') or 'on the screen'}: "
                              + " | ".join(t for _, t in sure))
            if doubt:
                around.append(f"{p.get('where') or 'on the screen'}, one engine only: " + " | ".join(doubt))
        if around:
            parts.append('<span class="sn-fine">around the window, on no window of its own: '
                         + esc("; ".join(around)) + "</span>\n")
        x0, y0, x1, y1 = s["entry"]["rect"]
        W, H = s["size"] or (0, 0)
        fp = [f"window {x0},{y0} to {x1},{y1} on the {W} by {H} frame, {s['entry'].get('where')}"
              + (f", {theme} style" if theme else "")]
        if s["entry"].get("top_from"):
            fp.append(f"its top read at {s['entry']['top_from']}")
        if s["entry"].get("drawn_over"):
            fp.append("drawn over the moving picture")
        if pointer:
            fp.append(f"the mouse pointer at {pointer['box'][0]},{pointer['box'][1]} "
                      f"(matched {pointer['score']:.2f} at scale {pointer['scale']})")
        if s.get("wobble"):
            times = ", ".join(ts for ts, _, _ in s["wobble"])
            wob = max(n for _, n, _ in s["wobble"])
            diffs = [(ts, d) for ts, _, d in s["wobble"] if d]
            line = f"the same screen read again at {times}"
            if wob:
                line += f"; letters wobbled in up to {wob} lines"
            if diffs:
                line += "; read differently: " + ", ".join(f"{d} lines at {ts}" for ts, d in diffs)
            fp.append(line + "; the fullest reading is drawn and the record holds each")
        for x in s["entry"].get("panel_extra") or []:
            fp.append(("read across the window, in no pane: " if x.get("confirmed") else "one engine only, across the window: ") + x["line"])
        fp.extend(fine)
        for p in s["panes"]:
            st = style_line(p)
            if st:
                fp.append(f"{p.get('where_in') or p.get('where') or 'pane'}: {st}")
        for m in s["moments"]:
            for p in s["panes"]:
                for n in p.get("notes") or []:
                    fp.append(str(n))
        parts.append('<span class="sn-fine">fine print: ' + esc("; ".join(dict.fromkeys(fp))) + "</span>\n")
        parts.append("---\n")
    desk = desktop_section(moments, sts)
    if desk:
        parts.append(desk + "\n\n---\n")
    parts.append(f"> [!note]- The moment-by-moment record, {len(moments)} moments (appendix)\n> ````text\n> "
                 + diary_text.rstrip("\n").replace("\n", "\n> ") + "\n> ````\n")
    return "\n".join(parts)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    text = note(path)
    if len(sys.argv) > 2:
        out = sys.argv[2]
        tmp = out + ".tmp-write"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, out)
        print(f"{out}: {len(text)} characters")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
