"""The look of a real window, scaled down, with the content the reader
read inside it.

A Finder window is drawn as Finder draws it: the traffic lights and the
sidebar with its icons and section labels, the toolbar with the folder's
name between the back and forward buttons, the list with its column
headings, disclosure triangles and folder icons, the selected row in the
colour that was measured, the striped empty rows below, the path bar.
An Obsidian window is drawn as Obsidian draws it: the browser behind it
when its tab strip was read, the title strip with the note's tab, the
ribbon, the file explorer with its header and tree, the note with its
inline title, its properties block and its body in the measured sizes
and weights. Everything written in a window was read off the frame;
only the furniture every such window has (buttons, icons, section
labels) is drawn from what the program always shows.

The classes are the vault's screen-notes style sheet, nothing else."""
import html as H
import re

import draw2

SECTIONS = {"Favorites", "Locations", "iCloud", "Tags"}
SIDE_GLYPH = {
    "Recents": "◷", "Shared": "⧉", "AirDrop": "⊚", "Applications": "Ⓐ", "Pictures": "▣", "Movies": "▤",
    "Music": "♪", "Desktop": "▭", "Documents": "▯", "Downloads": "⤓", "iCloud Drive": "☁",
    "Macintosh HD": "⊟", "Network": "⊕",
}
FOLDER_KIND = re.compile(r"^\s*Folder\b", re.I)

CANVAS_W = 960          # the drawn screen's width on the page, in pixels
CARD_W = 880            # the natural width a window is drawn at before scaling
ROW_H = 23.0            # a filled list row's height at that width
EMPTY_H = 17.0          # an empty striped row's height


def esc(s):
    return H.escape(str(s), quote=False)


def ico(kind):
    return f'<span class="sn-ico {kind}"></span>' if kind else '<span class="sn-ico"></span>'


# ---------------------------------------------------------------- Finder

def finder(st):
    table = st.main_table()
    if not table or not table.rows:
        return None
    side_words = list(table.side)
    # a strip of short words to the left of the list is its sidebar too;
    # what it holds that the list's own sidebar lacks goes in at its place
    tpart = next((q for q in st.parts if q["fam"] == "table" and q["model"] is table), None)
    for q in st.parts:
        if q["fam"] == "words" and tpart and q["x1"] is not None and tpart["x0"] is not None \
                and q["x1"] <= tpart["x0"] + 0.02 * (tpart["x1"] - tpart["x0"]) \
                and len(q["model"]) >= 3 and all(len(w) <= 24 for w in q["model"]):
            strip = [w for w in q["model"] if w in SECTIONS or w in SIDE_GLYPH or (w.count(" ") <= 1 and not w.endswith((".", ",")))]
            import draw3
            side_words = draw3.stitch(side_words, strip, key=lambda w: w) if side_words else strip
            break
    # the sidebar: lights at its top, then the items with their icons and
    # the section labels where they were read
    side = ""
    if side_words:
        items = ['<div class="sn-lights"></div>']
        for w in side_words:
            if w in SECTIONS:
                items.append(f'<div class="sn-section">{esc(w)}</div>')
            else:
                g = SIDE_GLYPH.get(w, "⌂" if w.lower() == (st.title or "").lower() or w.islower() else "▱")
                items.append(f'<div class="sn-item"><span class="sn-g">{g}</span>{esc(w)}</div>')
        side = '<div class="sn-side">' + "".join(items) + "</div>"
    # the toolbar: back and forward, the folder's name, the view and action buttons, search
    title = st.title or ""
    lights = "" if side else '<span class="sn-lights"></span>'
    toolbar = ('<div class="sn-toolbar">' + lights
               + '<span class="sn-btn">‹</span><span class="sn-btn">›</span>'
               + (f"<b>{esc(title)}</b>" if title else "<b>&nbsp;</b>")
               + '<span class="sn-grow"></span>'
               + '<span class="sn-btn">☰ ⌄</span><span class="sn-btn">⊞ ⌄</span>'
               + '<span class="sn-btn">⇪</span><span class="sn-btn">◇</span><span class="sn-btn">···</span>'
               + '<span class="sn-btn">⌕</span></div>')
    # the list
    head = list(table.header)
    n = max([len(head)] + [len(r["cells"]) for r in table.rows])
    head = head + [""] * (n - len(head))
    name_i = next((i for i, h in enumerate(head) if h == "Name"), 0)
    size_i = next((i for i, h in enumerate(head) if h == "Size"), None)
    kind_i = next((i for i, h in enumerate(head) if h.startswith("Kind")), None)
    out = ['<table class="sn-list">']
    if any(head):
        cells = []
        for i, h in enumerate(head):
            cells.append(f"<td>{esc(h)}" + (' <span class="sn-sort">˄</span>' if i == name_i and h else "") + "</td>")
        out.append('<tr class="sn-head">' + "".join(cells) + "</tr>")
    for r in table.rows:
        cells = list(r["cells"]) + [""] * (n - len(r["cells"]))
        it = list(r["italic"]) + [False] * (n - len(r["italic"]))
        kind = cells[kind_i] if kind_i is not None else ""
        if kind_i is not None:
            m = re.match(r"^(\d+\s?(?:bytes|KB|MB|GB))\s+(.*)$", kind)
            if m:
                cells[kind_i] = kind = m.group(2)
                if size_i is not None and not cells[size_i]:
                    cells[size_i] = m.group(1)
        # Is this row a folder or a file? What the Kind column says, first.
        # Then what the same name said in a moment where the Kind WAS read.
        # Then the colour of its icon, which was measured: across this video
        # a white icon was a file in every row whose Kind settled it, and a
        # green icon a folder in all but one; grey said nothing either way.
        # If none of that settles it, the row's nature was never on the
        # screen, and the drawing says so with an empty mark rather than
        # guessing from the shape of the name - plenty of folders are called
        # "00 Inbox" and plenty of files have no dot in them.
        name = cells[name_i]
        if kind:
            folder = bool(FOLDER_KIND.match(kind))
        elif r.get("folder") is not None:
            folder = bool(r["folder"])
        elif not r.get("band") and r.get("icon") in ("green", "white"):
            folder = r["icon"] == "green"
        elif size_i is not None and size_i < len(cells) and \
                re.match(r"^\s*[\d.]+\s*(bytes|KB|MB|GB|TB)\b", cells[size_i] or "", re.I):
            folder = False        # a folder is measured in items, never in bytes
        elif re.search(r"\.(md|json|log|txt|csv|png|jpe?g|pdf|zip|py|js|ts|html|css|ya?ml|sh)$",
                       name.strip(), re.I):
            folder = False        # the name carries the kind on its end
        else:
            folder = None
        tds = []
        for i, c in enumerate(cells):
            t = esc(c)
            if it[i] and c:
                t = f"<i>{t}</i>"
            if i == name_i:
                fico = "file md" if re.search(r"Markdo|\.md$", kind or cells[name_i]) else "file"
                if folder is None:
                    lead = '<span class="sn-tri"></span>' + ico("unknown")
                elif folder:
                    lead = '<span class="sn-tri">›</span>' + ico("")
                else:
                    lead = '<span class="sn-tri"></span>' + ico(fico)
                t = lead + t
            elif i == size_i and not c and folder:
                t = "--"
            tds.append(f"<td>{t}</td>")
        cls = f' class="sn-selected sn-band-{r["band"]}"' if r.get("band") else ""
        out.append(f"<tr{cls}>" + "".join(tds) + "</tr>")
    # the empty striped rows below the last file, as many as the real window
    # had room for: its shape, drawn at the card's width, less what the
    # toolbar, the headings and the path bar take
    # a couple of striped rows say "the list ended here"; padding a short
    # list out to the window's full height only makes the card long
    for _ in range(2):
        out.append(f'<tr class="sn-empty"><td colspan="{n}">&nbsp;</td></tr>')
    out.append("</table>")
    body = '<div class="sn-body">' + "".join(out) + "</div>"
    # the path bar
    foot = ""
    if table.path:
        crumbs = []
        for k, c in enumerate(table.path):
            g = '<span class="sn-g">⊟</span>' if k == 0 and c.lower().startswith("macintosh") else ico("")
            crumbs.append(f"<span>{g}{esc(c)}</span>")
        foot = '<div class="sn-pathbar">' + '<span class="sn-sep">›</span>'.join(crumbs) + "</div>"
    main = '<div class="sn-main">' + toolbar + body + foot + "</div>"
    cls = "sn-window sn-finder" + (" sn-dark" if st.theme == "dark" else "")
    if side:
        return f'<div class="{cls}"><div class="sn-cols sn-finder-cols">{side}{main}</div></div>'
    return f'<div class="{cls}">{main}</div>'


# -------------------------------------------------------------- Obsidian

def old_clock(t):
    import draw as old
    return bool(old.CLOCK.match(t.strip()))


def top_rows(st):
    """The words along the top of the frame, as rows: the menu bar first,
    then whatever strips sit under it (a browser's tabs, its address bar)."""
    items = [{"text": t, "box": [x0, y0, x1, y1], "ok": ok} for t, x0, y0, x1, y1, ok in st.topwords]
    rows = draw2.reading_order(items, lambda it: it["box"])
    return rows


def browser_behind(st):
    """The browser window behind Obsidian, when its tab strip and address
    bar were read along the top of the frame."""
    rows = top_rows(st)
    tabs, address, right = [], "", []
    for r in rows:
        texts = [it["text"] for it in r]
        joined = " ".join(texts)
        if re.search(r"Ask Google or type a URL|type a URL|https?://", joined):
            address = next((t for t in texts if re.search(r"URL|https?://", t)), joined)
            right += [t for t in texts if t != address and re.search(r"Relaunch|Gemini|update", t)]
        elif any(re.search(r"New Tab|YouTube|Facebook|Creating|×|tab", t) for t in texts) and len(texts) >= 2:
            # the tab strip, read at more than one moment: every tab once, by its place
            for it in r:
                if re.search(r"Gemini", it["text"]):
                    right.append(it["text"])
                elif not any(abs(it["box"][0] - x) < 40 for _, x in tabs) and not old_clock(it["text"]):
                    tabs.append((it["text"], it["box"][0]))
    joined_tabs = []
    for t, x in sorted(tabs, key=lambda tx: tx[1]):
        # a piece that starts mid-word is the tail of the tab before it
        if joined_tabs and (t[:1].islower() or t[:1] in "-–—"):
            joined_tabs[-1] = joined_tabs[-1] + t
        else:
            joined_tabs.append(t)
    tabs = joined_tabs
    if not (tabs or address):
        return ""
    def fold(words):
        keep = []
        for w in sorted(words, key=len, reverse=True):
            nw = re.sub(r"[^a-z0-9]", "", w.lower())
            if nw and not any(nw in re.sub(r"[^a-z0-9]", "", k.lower()) for k in keep):
                keep.append(w)
        out = []
        for w in words:
            if w in keep and w not in out:
                out.append(w)
        return out
    tabs, right = fold(tabs), fold(right)
    out = ['<div class="sn-browser">']
    if tabs:
        out.append('<div class="sn-tabs">' + "".join(
            f'<span class="sn-tab{" active" if t.strip() == "New Tab" else ""}">● {esc(t)} ×</span>' for t in tabs)
            + '<span class="sn-plus">+</span>'
            + "".join(f'<span class="sn-right">{esc(t)}</span>' for t in right if "Gemini" in t) + "</div>")
    if address:
        out.append('<div class="sn-toolbar sn-address"><span class="sn-btn">‹</span><span class="sn-btn">›</span><span class="sn-btn">↻</span>'
                   + f'<span class="sn-urlbar">G &nbsp;{esc(address)}</span>'
                   + "".join(f'<span class="sn-btn sn-right">{esc(t)}</span>' for t in right if "Gemini" not in t) + "</div>")
    out.append("</div>")
    return "".join(out)


def obsidian(st, behind=True):
    tree = st.tree()
    doc = st.main_doc()
    if not (tree or doc):
        return None
    title = ""
    if doc:
        title = doc.title()
    strip = browser_behind(st) if behind else ""
    toolbar = ('<div class="sn-toolbar sn-obsidian-bar"><span class="sn-lights"></span>'
               '<span class="sn-btn">▱</span><span class="sn-btn">⌕</span><span class="sn-btn">☆</span>'
               + (f'<span class="sn-tab active">{esc(title)} &nbsp;×</span>' if title else "")
               + '<span class="sn-plus">+</span><span class="sn-grow"></span></div>')
    ribbon = '<div class="sn-ribbon">' + "".join('<span class="sn-g">' + g + "</span>" for g in "▯⌬⊞▦⊡›≣") + "</div>"
    cols = [ribbon]
    if tree:
        lines = []
        for t, h in tree.lines:
            lead = t[:len(t) - len(t.lstrip("│ "))]
            rest = t[len(lead):]
            guides = esc(lead).replace("│", '<span class="sn-guide">│</span>')
            chev = ""
            if rest[:1] in "˃˅":
                chev = f'<span class="sn-chev">{"›" if rest[0] == "˃" else "⌄"}</span> '
                rest = rest[1:].lstrip()
            else:
                rest = rest.lstrip()
            # a row the screen set in bold is marked with stars in the
            # record; the drawing sets it in bold, it does not print stars
            body = esc(rest)
            body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
            body = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", body)
            body = body.replace("**", "").replace("*", "")
            if "<i>" in h:
                body = f"<i>{body}</i>"      # a name no engine read cleanly
            m = re.search(r'<span class="(sn-[a-z]+)"', h)
            if m:
                body = f'<span class="{m.group(1)}" style="font-weight:600">{body}</span>'
            lines.append(guides + chev + body)
        count = getattr(st, "explorer_count", "")
        explorer = ('<div class="sn-explorer"><div class="sn-explorer-head"><span class="sn-g">✎</span><span class="sn-g">▱+</span>'
                    '<span class="sn-g">⇅</span><span class="sn-g">⊟</span><span class="sn-g">⌃</span></div>'
                    + (f'<div class="sn-count">{esc(count)}</div>' if count else "")
                    + '<div class="sn-tree">' + "".join(f"<div>{l}</div>" for l in lines) + "</div></div>")
        cols.append(explorer)
    if doc:
        # How far down the pane the note had been scrolled matters in a
        # picture of the screen, where the text has to sit where it sat.
        # On the window's own card it is only a hole at the top: the card
        # is the window rebuilt to READ, so it starts at its first line.
        pad = getattr(st, "_doc_pad", 0) if (not behind and getattr(st, "shape", None)) else 0
        wide = getattr(st, "_doc_wide", 0)
        bits = ([f"padding-top:{pad}px"] if pad else []) + \
               ([f"--sn-line:{wide}%"] if wide and wide < 98 else [])
        sty_doc = f' style="{";".join(bits)}"' if bits else ""
        cols.append(f'<div class="sn-doc"{sty_doc}>' + note_html(st, doc, title) + "</div>")
    grid = "30px " + ("minmax(180px, 38fr) " if tree else "") + ("62fr" if doc else "")
    body = f'<div class="sn-cols sn-obsidian-cols" style="grid-template-columns: {grid.strip()}">' + "".join(cols) + "</div>"
    cls = "sn-window sn-obsidian" + (" sn-dark" if st.theme == "dark" else "")
    return f'<div class="{cls}">{strip}{toolbar}{body}</div>'


def note_html(st, doc, title):
    """The note as Obsidian shows it: the tab's header line, the inline
    title, the properties block, then the body in its measured sizes."""
    out = []
    if title:
        out.append(f'<div class="sn-crumb">‹ &nbsp;› &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{esc(title)}</div>')
    lines = [(t, h) for t, h in doc.lines if re.search(r"[A-Za-z0-9]", t) or t.startswith("---")]
    first = True
    add_property = any(re.search(r"Add\s*property", t) for t, *_ in st.topwords) or any(
        re.search(r"Add\s*property", w) for w in st.words())
    props_done = False
    for t, h in lines:
        plain = t.strip().strip("#*> ").strip()
        if first and len(plain) <= 40 and not t.startswith("---") and '<div class="sn-h' not in h:
            out.append(f'<div class="sn-title">{esc(plain)}</div>')
            first = False
            continue
        first = False
        if t.startswith("---props"):
            m = re.search(r'<div class="sn-props">(.*?)</div>', h)
            pairs = (m.group(1) if m else "").split("<br>")
            rows = []
            for pr in pairs:
                k, _, v = H.unescape(pr).partition(":")
                if k.strip():
                    rows.append(f'<div class="sn-prop"><span class="sn-g">☰</span><span class="sn-key">{esc(k.strip())}</span><span class="sn-val">{esc(v.strip())}</span></div>')
            out.append('<div class="sn-props"><div class="sn-props-head">Properties</div>' + "".join(rows)
                       + ('<div class="sn-prop sn-addprop">+ Add property</div>' if add_property else "") + "</div>")
            props_done = True
            continue
        out.append(bulleted(h))
    if st.covered:
        out.append('<span class="sn-covered">the camera picture covered this corner of the window</span>')
    return "".join(out)


def bulleted(h):
    """A line that begins with a list marker is drawn as a bullet with a
    hanging indent, as the program draws it."""
    m = re.match(r'^(<div(?: class="[^"]*")?>)((?:&nbsp;)*)\s*([*\-•]) (.*)$', h)
    if not m:
        return h
    tag, indent, _, rest = m.groups()
    rest = re.sub(r"</div>\s*$", "", rest)
    depth = len(indent) // 12
    cls = ' class="sn-li"' if 'class="' not in tag else tag[4:-1].replace('class="', 'class="sn-li ')
    return f'<div{cls} style="margin-left:{depth * 14}px"><span class="sn-bullet">•</span><span class="sn-litext">{rest}</span></div>'


# ------------------------------------------------------------------ entry

def window(st, behind=True):
    """The window drawn in its program's look, or None when no look is
    known for it (the plain drawing then stands). With behind off, nothing
    that sat behind the window is drawn inside it -- the screen picture
    draws those where they really were."""
    try:
        if st.name == "The Finder window":
            return finder(st)
        if st.name == "The Obsidian window":
            return obsidian(st, behind=behind)
    except Exception as e:      # a drawing must never take the note down
        import sys
        FELL.append((st.name, list(st.times[:1]), repr(e)))
        print(f"furnish: {st.name} {st.times[:1]}: {e!r}", file=sys.stderr)
    return None


# A window that falls back to the plain drawing still writes a note, so the
# fault is invisible in the finished file: the window is simply poorer than
# it should be. Every fall is kept here so the build can count them and
# refuse the note, the same way it refuses one that breaks a drawing rule.
FELL: list = []


# ---------------------------------------------------------------- the screen



BAR = 0.026            # the desktop bar's share of the screen's height


def clip_box(rect, W, H, bar=True):
    """A window cannot stand outside the screen it was on. An edge measured
    past the frame is a measurement that slipped, and drawing it makes a
    window taller than the desktop, so the box is cut back to the screen -
    which is also what the screen itself did to the window."""
    x0, y0, x1, y1 = rect
    if bar:
        y0 = max(y0, BAR * H)      # nothing sits on top of the desktop bar
    x0 = min(max(float(x0), 0.0), float(W))
    x1 = min(max(float(x1), 0.0), float(W))
    y0 = min(max(float(y0), 0.0), float(H))
    y1 = min(max(float(y1), 0.0), float(H))
    return [x0, y0, max(x1, x0 + 8), max(y1, y0 + 8)]


def off_screen(rect, W, H):
    """How much of a measured box fell outside the screen, as a share of the
    box. Anything much above nothing means the edges are not to be trusted."""
    x0, y0, x1, y1 = rect
    area = max(1.0, (float(x1) - x0) * (float(y1) - y0))
    ix = max(0.0, min(float(x1), float(W)) - max(float(x0), 0.0))
    iy = max(0.0, min(float(y1), float(H)) - max(float(y0), 0.0))
    return max(0.0, 1.0 - (ix * iy) / area)


def slot_style(rect, W, H, bar=True):
    x0, y0, x1, y1 = clip_box(rect, W, H, bar=bar)
    return (f"left:{100.0 * x0 / W:.2f}%;top:{100.0 * y0 / H:.2f}%;"
            f"width:{100.0 * (x1 - x0) / W:.2f}%;height:{100.0 * (y1 - y0) / H:.2f}%")


UI_TXT = 7.0        # a line of screen text, in canvas pixels, at the base zoom
CSS_TXT = 11.5      # the same line as the style sheet draws it
# How far apart the screen set one row from the next, in canvas pixels at the
# base zoom, measured off the frame. This is what a drawn window is scaled by:
# a row's PITCH is the thing both the screen and the style sheet have, where a
# glyph's measured box and a style sheet's font-size are not the same quantity
# at all and comparing them drew every list a third too tall.
UI_ROW = 0.0


def scaled(html, rect, W, kz=1.0, cls="sn-slot", extra=""):
    """A window drawn so its text stands the height the frame gave it: the
    sheet's writing shrunk to the screen's, and the window's own layout
    spread over the width its rectangle really had."""
    wide = max(1.0, rect[2] - rect[0])
    step = (UI_ROW / ROW_H) if UI_ROW else (UI_TXT / CSS_TXT)
    k = max(0.05, kz * step)
    w_css = (CANVAS_W * wide / W) / k
    tall = w_css * (rect[3] - rect[1]) / wide
    html = re.sub(r'^(<div class="sn-window[^"]*")',
                  r'\1 style="min-height:%dpx"' % max(0, round(tall)), html, count=1)
    return (f'<div class="{cls}" style="{extra}">'
            f'<div class="sn-shot" style="width:{w_css:.0f}px;transform:scale({k:.4f})">{html}</div></div>')


def _shares(a, b):
    """How much of the smaller box the two have in common, nought to one."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (w * h) / max(1.0, small)


def _within(a, b):
    """How much of box a lies inside box b, nought to one. Which way round
    matters: a small window sitting inside a big one is covered by it, while
    the big one is barely touched."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    return (w * h) / max(1.0, (a[2] - a[0]) * (a[3] - a[1]))


def _close(a, b):
    """Two outlines in the same place, near enough to be the one window."""
    wide = max(1.0, min(a[2] - a[0], b[2] - b[0]))
    tall = max(1.0, min(a[3] - a[1], b[3] - b[1]))
    return (abs(a[0] - b[0]) < 0.15 * wide and abs(a[2] - b[2]) < 0.15 * wide
            and abs(a[1] - b[1]) < 0.15 * tall and abs(a[3] - b[3]) < 0.15 * tall)


def deskbar(bar_words, clock):
    def word(w):
        # a menu name only one engine read is marked the way every other
        # one-engine reading in the note is marked
        if w.startswith("<i>") and w.endswith("</i>"):
            return f"<span><i>{esc(w[3:-4])}</i></span>"
        return f"<span>{esc(w)}</span>"
    left = "".join(word(w) for w in bar_words[:14])
    right = f"<span class=\"sn-right\">{esc(clock)}</span>" if clock else ""
    return f'<div class="sn-deskbar">{left}{right}</div>'


def screen_shot(span, subjects, W, H, bar_words, clock, behind_cards=(),
                ghosts=(), camera=None, sure=True, kz=1.0):
    """The layout of the screen over one stretch of time: the desktop bar
    with its own words, the window this stretch is about filled in with
    what it really said, and every other window standing where it stood,
    at the shape it had, drawn as a labelled outline. No picture is ever
    pasted in -- where the camera lay, an outline says so."""
    barred = bar_words is not None
    out = [f'<div class="sn-screen" style="aspect-ratio:{W} / {H}">']
    if barred:
        out.append(deskbar(bar_words, clock))
    drawn = []
    names = []          # every outline's name, drawn last so none is hidden

    placed = []

    def outline(box, tag, cls="sn-ghost", extra=""):
        lab = ""
        # When the desktop bar is in view the picture holds the whole screen,
        # so a window measured half outside it cannot be right and is drawn
        # the way anything unsure is drawn. With no bar the video was zoomed
        # into a part of the screen, and a window running past the edge is
        # exactly what was there.
        if barred and off_screen(box, W, H) > 0.25 and "sn-away" not in cls:
            cls += " sn-away"
        if tag:
            # two windows whose top-left corners nearly meet would print
            # their names over each other, so each later one steps down
            l = 100.0 * box[0] / max(1, W)
            t = 100.0 * box[1] / max(1, H)
            step = sum(1 for pl, pt in placed if abs(pl - l) < 14 and abs(pt - t) < 5)
            placed.append((l, t))
            off = f'top:{5 + step * 15}px;' if step else ""
            # the name is drawn last and over everything, because a window
            # filled in on top of this one would otherwise hide it and the
            # outline would stand there unnamed
            mod = " sn-away" if "sn-away" in cls else (" sn-subject" if "sn-subject" in cls else "")
            # the placing is written into the tag itself, not left to the
            # style sheet: a name box is a NEW class, and a picture must
            # not fall apart on a reader whose snippet has not caught up
            names.append(f'<div class="sn-ghost-name{mod}" style="position:absolute;'
                         f'{slot_style(box, W, H, bar=barred)};z-index:40;'
                         f'border:0;background:none;pointer-events:none">'
                         f'<span class="sn-ghost-tag" style="{off}">{esc(tag)}</span></div>')
        return (f'<div class="{cls}" style="{slot_style(box, W, H, bar=barred)}{extra}">'
                + lab + "</div>")

    def uncover(rect, on_frame=False):
        """A window behind is drawn only because it was SEEN, so the window
        in front cannot have been standing over it. Where the front window's
        box swallows a strip that was plainly in view - a row of tabs above
        it, a bar down its side - the box reached too far, and it is pulled
        back to the edge of what was showing.

        A box the frame itself drew is never pulled back. Its edges were
        measured off the screen; a box worked out from where words sat is a
        guess, and a guess does not get to move a measurement."""
        if on_frame:
            return list(rect)
        x0, y0, x1, y1 = rect
        w, h = max(1.0, x1 - x0), max(1.0, y1 - y0)
        for b in drawn:
            bx0, by0, bx1, by1 = b
            if min(x1, bx1) - max(x0, bx0) <= 0 or min(y1, by1) - max(y0, by0) <= 0:
                continue
            wide = (min(x1, bx1) - max(x0, bx0)) >= 0.6 * w
            tall = (min(y1, by1) - max(y0, by0)) >= 0.6 * h
            if wide and by1 - y0 > 0 and by1 - y0 <= 0.25 * h and by0 <= y0 + 0.02 * h:
                y0 = by1                      # a strip lying across the top
            elif tall and bx1 - x0 > 0 and bx1 - x0 <= 0.25 * w and bx0 <= x0 + 0.02 * w:
                x0 = bx1                      # a bar standing down the side
        return [x0, y0, max(x1, x0 + 8), max(y1, y0 + 8)]

    # The boxes the front windows really filled are settled first: a window
    # behind is drawn because it was SEEN, and whether it was seen depends
    # on what stood over it.
    shown = []
    for tag, box in behind_cards:
        drawn.append(clip_box(box, W, H, bar=barred))
    fronts = []
    for st, rect in subjects:
        fronts.append((st, uncover(clip_box(rect, W, H, bar=barred),
                                   getattr(st, "_on_frame", False)) if rect else None))
    solid = [r for _, r in fronts if r]

    def in_view(box):
        """What is left of a window once the windows in front are over it.
        Covered whole, it was not on the screen, and drawing its outline
        would put back something the video never showed."""
        return max((_within(box, r) for r in solid), default=0.0) < 0.92

    # the windows standing behind, and the places words were read that no
    # window of this stretch owns
    # the biggest first, so a window's older place - the same window before
    # it was navigated, still carried in the record - does not get a second
    # outline inside the one that is really showing
    marks = []          # [box, tag, class] - gathered first, then merged
    for tag, box in behind_cards:
        box = clip_box(box, W, H, bar=barred)
        if in_view(box):
            marks.append([box, tag, "sn-ghost"])
    for box, tag, kind in ghosts:
        if not box:
            continue
        box = clip_box(box, W, H, bar=barred)
        if any(_within(box, d) > 0.5 for d in drawn) or not in_view(box):
            continue
        if any(_close(box, d) for d in drawn):
            continue
        drawn.append(box)
        marks.append([box, tag, "sn-ghost sn-away" if kind == "away" else "sn-ghost"])

    # One place, one window. Two outlines over the same ground are the same
    # window twice - a window's older place still carried in the record, or a
    # patch of words that turned out to belong to a window already named. The
    # two become one: the name that says something, over the box the words
    # themselves reach to.
    merged = []
    for box, tag, cls in marks:
        for other in merged:
            a = (box[2] - box[0]) * (box[3] - box[1])
            b = (other[0][2] - other[0][0]) * (other[0][3] - other[0][1])
            # a strip lying inside a window is a window IN FRONT of it, not
            # the same window read twice; only boxes of a like size are one
            # window seen twice
            like = min(a, b) / max(1.0, max(a, b)) > 0.5
            # two outlines carrying the SAME name, one standing inside the
            # other, are that one window twice over whatever their sizes:
            # a window cannot stand in front of itself
            # the same program, one box inside the other, is that one window
            # twice: a stretch that could not name its folder says only
            # "Finder", and the fuller name belongs to the same window
            same = bool(tag) and bool(other[1]) and \
                tag.split(":")[0].strip() == other[1].split(":")[0].strip()
            share = max(_within(box, other[0]), _within(other[0], box))
            if (like and (share > 0.85 or _close(box, other[0]))) or (same and share > 0.5):
                if (box[2] - box[0]) * (box[3] - box[1]) > \
                        (other[0][2] - other[0][0]) * (other[0][3] - other[0][1]):
                    other[0] = box
                if len(tag) > len(other[1]) and not tag.startswith("a window"):
                    other[1] = tag
                if "sn-away" not in cls:
                    other[2] = cls
                break
        else:
            merged.append([box, tag, cls])
    for box, tag, cls in merged:
        shown.append(box)
        out.append(outline(box, tag, cls))

    # the windows this stretch is about: the top layer, drawn with its real
    # content at a size that reads, cut off by the edges of the box it
    # really stood in
    for z, (st, rect) in enumerate(fronts):
        if not rect:
            continue
        st.shape = rect
        html = window(st, behind=False) or st.plain_window_html()
        st.shape = None
        if not html:
            out.append(outline(rect, getattr(st, "_label", "") or "",
                               "sn-ghost sn-subject", f";z-index:{3 + z}"))
            continue
        # The window is drawn to SCALE inside its rectangle: the card is laid
        # out over the width that rectangle really had, and the style
        # sheet's writing is shrunk to the height the screen's writing had,
        # so a line of text stands in the same proportion to its window as
        # it did in the video. Drawing the card at reading size and cutting
        # it off at the box shows a corner of a window at the wrong scale,
        # which is not a picture of that screen.
        out.append(scaled(html, clip_box(rect, W, H, bar=barred), W, kz=kz,
                          extra=f'{slot_style(rect, W, H, bar=barred)};z-index:{3 + z}'))
    if camera:
        cbox = camera[0] if isinstance(camera, (tuple, list)) else camera
        out.append(f'<div class="sn-camera" style="{slot_style(cbox, W, H, bar=barred)}">'
                   f'<span class="sn-camera-tag">the camera picture</span></div>')
    out.extend(names)
    stamp = span["t0"] if span["t0"] == span["t1"] else f"{span['t0']} to {span['t1']}"
    if not sure:
        stamp += " \u00b7 edges taken from where its words sat"
    out.append(f'<div class="sn-stamp">{esc(stamp)}</div>')
    out.append("</div>")
    return ('<div class="sn-stage">' + "".join(out) + "</div>")


