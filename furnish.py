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
        # what the Kind column says, first; a green icon means a folder only
        # where no kind was read and no selection colour could have stained it
        name = cells[name_i]
        if kind:
            folder = bool(FOLDER_KIND.match(kind))
        elif r.get("icon") == "green" and not r.get("band"):
            folder = True
        else:
            folder = "." not in name and not re.search(r"\d", name)
        tds = []
        for i, c in enumerate(cells):
            t = esc(c)
            if it[i] and c:
                t = f"<i>{t}</i>"
            if i == name_i:
                fico = "file md" if re.search(r"Markdo|\.md$", kind or cells[name_i]) else "file"
                lead = ('<span class="sn-tri">›</span>' + ico("")) if folder else ('<span class="sn-tri"></span>' + ico(fico))
                t = lead + t
            elif i == size_i and not c and folder:
                t = "--"
            tds.append(f"<td>{t}</td>")
        cls = f' class="sn-selected sn-band-{r["band"]}"' if r.get("band") else ""
        out.append(f"<tr{cls}>" + "".join(tds) + "</tr>")
    # the empty striped rows below the last file, as many as the real window
    # had room for: its shape, drawn at the card's width, less what the
    # toolbar, the headings and the path bar take
    empty = 2
    rect = getattr(st, "shape", None) or st.rect
    if rect and rect[2] > rect[0]:
        tall = CARD_W * (rect[3] - rect[1]) / (rect[2] - rect[0])
        room = tall - 40 - 26 - (30 if table.path else 0) - len(table.rows) * ROW_H
        empty = int(max(2, min(60, room / EMPTY_H)))
    for _ in range(empty):
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
    out.append('<div class="sn-behind">the browser window, behind; Obsidian sits in front of it from here down</div></div>')
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
            body = esc(rest)
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
                    + '<div class="sn-tree">' + "\n".join(lines) + "</div></div>")
        cols.append(explorer)
    if doc:
        cols.append('<div class="sn-doc">' + note_html(st, doc, title) + "</div>")
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
        print(f"furnish: {st.name} {st.times[:1]}: {e!r}", file=sys.stderr)
    return None


# ---------------------------------------------------------------- the screen



BAR = 0.026            # the desktop bar's share of the screen's height


def slot_style(rect, W, H):
    x0, y0, x1, y1 = rect
    y0 = max(y0, BAR * H)          # nothing sits on top of the desktop bar
    y1 = max(y1, y0 + 8)
    return (f"left:{100.0 * x0 / W:.2f}%;top:{100.0 * y0 / H:.2f}%;"
            f"width:{100.0 * (x1 - x0) / W:.2f}%;height:{100.0 * (y1 - y0) / H:.2f}%")


def scaled(html, rect, W, cls="sn-slot", extra=""):
    """A window drawn at its natural size, then shrunk to the share of the
    screen it really took."""
    wide = max(1.0, rect[2] - rect[0])
    k = (CANVAS_W * wide / W) / CARD_W
    return (f'<div class="{cls}" style="{extra}">'
            f'<div class="sn-shot" style="transform:scale({k:.4f})">{html}</div></div>')


def deskbar(bar_words, clock):
    left = "".join(f"<span>{esc(w)}</span>" for w in bar_words[:8])
    right = f"<span class=\"sn-right\">{esc(clock)}</span>" if clock else ""
    return f'<div class="sn-deskbar">{left}{right}</div>'


def screen_shot(span, subject, W, H, bar_words, clock, tag_of, behind_states=(), skip=None, rect=None):
    """One picture of the whole screen: every window where it sat and at the
    size it was, the one being shown filled in, the others as outlines."""
    ch = CANVAS_W * H / max(1, W)
    out = [f'<div class="sn-screen" style="height:{ch:.0f}px">', deskbar(bar_words, clock)]
    # a window that never shows in full anywhere gets its content drawn
    # where it sat, because this is its only chance to be seen
    for back, box, html in behind_states:
        box = [box[0], max(box[1], BAR * H), box[2], box[3]]
        out.append(scaled(html, box, W, cls="sn-slot sn-partial", extra=slot_style(box, W, H)))
    import draw3
    fixed = span.get("rects") or {}
    skip = skip if skip is not None else subject
    for other in span["states"]:
        if other is skip or other is subject:
            continue
        box = fixed.get(id(other)) or draw3.span_rect(other, span["t0"])
        if not box:
            continue
        tag = tag_of(other)
        out.append(f'<div class="sn-ghost" style="{slot_style(box, W, H)}">'
                   + (f'<span class="sn-ghost-tag">{esc(tag)}</span>' if tag else "") + "</div>")
    rect = rect or fixed.get(id(subject)) or draw3.span_rect(subject, span["t0"]) or subject.rect
    subject.shape = rect
    html = window(subject, behind=False) or subject.plain_window_html()
    # the card is given the window's own shape, so it fills its place the
    # way the window filled the screen
    if rect and rect[2] > rect[0]:
        tall = CARD_W * (rect[3] - rect[1]) / (rect[2] - rect[0])
        html = re.sub(r'^(<div class="sn-window[^"]*")', r'\1 style="min-height:%dpx"' % round(tall), html, count=1)
    out.append(scaled(html, rect, W, extra=slot_style(rect, W, H) + ";z-index:3"))
    stamp = span["t0"] if span["t0"] == span["t1"] else f"{span['t0']} to {span['t1']}"
    out.append(f'<div class="sn-stamp">{esc(stamp)}</div>')
    out.append("</div>")
    return "".join(out)
