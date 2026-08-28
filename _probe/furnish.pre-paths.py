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

SIDE_FLAT = {re.sub(r"[^a-z0-9]+", "", n.lower()) for n in draw2.SIDE_NAMES} \
    | {re.sub(r"[^a-z0-9]+", "", n.lower()) for n in SECTIONS}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def side_words_of(st):
    """A Finder window's fixed favorites sidebar, as its list of names.

    Two sources, in order: the list's own sidebar column (`table.side`), and
    a strip of short words the reader filed to the LEFT of the list -- the
    favorites (Recents, Shared, Applications, ...) read as a pane of their
    own. The sidebar is fixed furniture: a window that showed it one moment
    showed it the next, so a stretch that read only part of it, or none, is
    filled from the window's whole reading. Factored out of `finder` so the
    drawing side can carry it into a stretch that missed it."""
    table = st.main_table()
    side_words = list(table.side) if table else []
    # a stretch that never read this window's sidebar, though the window
    # plainly showed one, carries the house favorites in (set on the state by
    # the drawing side, which alone knows the favorites were on the screen).
    # This runs even with no list at all: a Finder window standing behind
    # another shows only its sidebar, its file list hidden, so it has a
    # sidebar and no table.
    if not side_words and getattr(st, "_carried_side", None):
        side_words = list(st._carried_side)
    tpart = (next((q for q in st.parts if q["fam"] == "table" and q["model"] is table), None)
             if table else None)
    for q in st.parts:
        if q["fam"] == "words" and tpart and q["x1"] is not None and tpart["x0"] is not None \
                and q["x1"] <= tpart["x0"] + 0.02 * (tpart["x1"] - tpart["x0"]) \
                and len(q["model"]) >= 3 and all(len(w) <= 24 for w in q["model"]):
            strip = [w for w in q["model"] if w in SECTIONS or w in SIDE_GLYPH or (w.count(" ") <= 1 and not w.endswith((".", ",")))]
            import draw3
            side_words = draw3.stitch(side_words, strip, key=lambda w: w) if side_words else strip
            break
    return side_words


def finder(st):
    table = st.main_table()
    side_words = side_words_of(st)
    rows = table.rows if (table and table.rows) else []
    # A FINDER'S LIST READ AS A TREE IS STILL ITS LIST. With only its Name
    # column in view, a file list comes back as a plain column of names and
    # the reader files it as a file tree. At 00:00:30 the vault-demo window's
    # two panes both came back that way - its favorites and its files - so
    # the state carried no table at all, and the card drew the window with
    # its sidebar, its title and an EMPTY list where the screen showed ten
    # rows. The names are all there in the reading. This window is a Finder
    # by its own title bar, so its names are drawn as the list they are, and
    # nothing is invented: no dates, no sizes, no kinds, only what was read.
    # The favorites are kept out of it, since those are the sidebar.
    if not rows:
        # NOT `st.tree()`, WHICH IS THE LARGEST AND CAN BE THE SIDEBAR. Here
        # both panes came back as trees with ten lines each and the larger
        # was the favorites, so the list drawn would have been Recents,
        # Shared, Applications... The list is the tree whose lines are NOT
        # the fixed favorites, and where two qualify it is the rightmost -
        # a Finder's files stand to the right of its sidebar.
        def _clean(model):
            out = []
            for t_, _ in (model.lines if model else ()):
                nm = t_.strip("\u2502 \u02c3\u02c5\u25b8\u25be").strip()
                if nm:
                    out.append(nm)
            return out
        best, best_x = None, None
        for q in st.parts:
            if q["fam"] != "tree":
                continue
            got = _clean(q["model"])
            if not got:
                continue
            side_like = sum(1 for nm in got if norm(nm) in SIDE_FLAT)
            if side_like * 2 >= len(got):
                continue                      # this one is the favorites
            x0 = q["x0"] if q["x0"] is not None else -1
            if best is None or x0 > best_x:
                best, best_x = got, x0
        if best and len(best) >= 3:
            rows = [{"cells": [nm], "italic": [False]} for nm in best]
    # A Finder window is drawable with a list, OR with only its sidebar and
    # no list at all -- a window standing behind another shows just its
    # favorites down the left, its file area hidden. Without one of the two
    # there is nothing of a Finder to draw, and the plain window stands.
    if not rows and not side_words:
        return None
    # the sidebar: lights at its top, then the items with their icons and
    # the section labels where they were read
    side = ""
    if side_words:
        items = ([] if getattr(st, "_cut_left", False)
                 else ['<div class="sn-lights"></div>'])
        for w in side_words:
            if w in SECTIONS:
                items.append(f'<div class="sn-section">{esc(w)}</div>')
            else:
                g = SIDE_GLYPH.get(w, "⌂" if w.lower() == (st.title or "").lower() or w.islower() else "▱")
                items.append(f'<div class="sn-item"><span class="sn-g">{g}</span>{esc(w)}</div>')
        side = '<div class="sn-side">' + "".join(items) + "</div>"
    # the toolbar: back and forward, the folder's name, the view and action buttons, search
    title = st.title or ""
    # A WINDOW THE SCREEN CUT OFF DOWN ITS LEFT EDGE HAS NO CORNER ON SHOW.
    # Its three round buttons and its back and forward arrows stand outside
    # the frame, so drawing them puts on the page what the screen never had.
    # The rest of the toolbar - the folder's name and the buttons on the
    # right - is where the window really did carry it.
    cut_left = bool(getattr(st, "_cut_left", False))
    lights = "" if (side or cut_left) else '<span class="sn-lights"></span>'
    arrows = ("" if cut_left else
              '<span class="sn-btn">‹</span><span class="sn-btn">›</span>')
    toolbar = ('<div class="sn-toolbar">' + lights + arrows
               + (f"<b>{esc(title)}</b>" if title else "<b>&nbsp;</b>")
               + '<span class="sn-grow"></span>'
               + '<span class="sn-btn">☰ ⌄</span><span class="sn-btn">⊞ ⌄</span>'
               + '<span class="sn-btn">⇪</span><span class="sn-btn">◇</span><span class="sn-btn">···</span>'
               + '<span class="sn-btn">⌕</span></div>')
    # the list
    head = list(table.header) if table else []
    n = max([len(head)] + [len(r["cells"]) for r in rows] + [1])
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
    for r in rows:
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
    # A COUPLE OF STRIPED ROWS SAY "THE LIST ENDED HERE", and no more than
    # that. Finder stripes every empty row from the last file down to the
    # path bar, and filling the card the same way covers more of the frame's
    # ink - measured, `real` rose on eight pictures. It is still forbidden:
    # "Padded rows, a stretched window, type at the wrong scale" stand
    # together in this job's list of things the drawing may never do, and
    # `selfcheck` fails a note that pads a window. So the window drawn at
    # the screen's own row spacing ends its list where the list ends, and
    # the frame's striped filler below it is ink the picture will not cover.
    for _ in range(2):
        out.append(f'<tr class="sn-empty"><td colspan="{n}">&nbsp;</td></tr>')
    out.append("</table>")
    body = '<div class="sn-body">' + "".join(out) + "</div>"
    # the path bar
    foot = ""
    if table and table.path:
        # A PATH NEVER PASSES THROUGH THE SAME FOLDER TWICE. A window's path
        # is gathered across the moments it was read, and where the same bar
        # was read more than once the crumbs come back one after another:
        # the drawn bar read `... > .claude > projects > Usersjaredrhodenizer
        # > jaredrhodenizer > .claude > projects > ...`, three times round.
        # It ends at the first crumb it has already passed.
        # ...and what says so is a run that comes back, not a repeated word.
        # The bar reads as `Users > jared > .claude > projects` TWICE and then
        # continues `Documents > vault-demo > 02 Company A` - a real tail. Both
        # earlier attempts cut at the first repeat and threw that tail away,
        # which cost ink on seven pictures. So collapse the duplicated run
        # where it sits and keep what stands on either side of it.
        path_ = [c for c in table.path]
        keys = [re.sub(r"[^a-z0-9]+", "", str(c).lower()) for c in path_]
        again = True
        while again:
            again = False
            for ln in range(len(keys) // 2, 0, -1):
                for i in range(len(keys) - 2 * ln + 1):
                    if keys[i:i + ln] == keys[i + ln:i + 2 * ln]:
                        del path_[i + ln:i + 2 * ln]
                        del keys[i + ln:i + 2 * ln]
                        again = True
                        break
                if again:
                    break
        crumbs = []
        for k, c in enumerate(path_):
            g = '<span class="sn-g">⊟</span>' if k == 0 and c.lower().startswith("macintosh") else ico("")
            crumbs.append(f"<span>{g}{esc(c)}</span>")
        foot = '<div class="sn-pathbar">' + '<span class="sn-sep">›</span>'.join(crumbs) + "</div>"
    # THE PATH BAR SITS AT THE WINDOW'S FOOT, because that is where Finder
    # puts it. Drawn straight under the last file it rides up the window
    # whenever the list is short, and once the rows are drawn at the
    # screen's own spacing instead of about twice it, every list is short.
    # Measured, that left one band wrong in every picture holding a Finder:
    # "16-91% across, 67-80% down" missing, which is the window's whole
    # lower edge, its bar included. The list takes the slack instead. This
    # pads nothing - the empty rows stay two and the space below the list
    # stays empty, which is what the rule requires.
    main = ('<div class="sn-main" style="display:flex;flex-direction:column;'
            'flex:1 1 auto;min-height:0">' + toolbar
            + '<div style="flex:1 1 auto;min-height:0">' + body + '</div>'
            + foot + "</div>")
    cls = "sn-window sn-finder" + (" sn-dark" if st.theme == "dark" else "")
    if side:
        # a sidebar the frame MEASURED is drawn at the width it was; the
        # card's fixed one stands for every Finder that was never measured
        share = getattr(st, "side_share", None)
        cols = (f' style="grid-template-columns: {share * 100:.1f}% 1fr"'
                if share else "")
        grid = (cols[:-1] + ';flex:1 1 auto;min-height:0"') if cols else \
            ' style="flex:1 1 auto;min-height:0"'
        return (f'<div class="{cls}"><div class="sn-cols sn-finder-cols"{grid}>'
                f'{side}{main}</div></div>')
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
    tree_ch = 0             # the tree's own longest row, set where the rows are built
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
        # HOW WIDE THE TREE HAS TO BE TO SHOW WHAT WAS READ OFF IT. The
        # column is sized as a share of the window, which is right and is
        # measured off the frame -- and at 00:00:00 Obsidian stands full
        # screen with its sidebar at 392 of 3840 pixels, a true 10%. Ten
        # percent of a 3840px screen is 392px and shows every name; ten
        # percent of a 700px card is 70px and shows none of them. The share
        # is accurate and the card is small, so the share alone cannot be the
        # whole answer here: a card exists to be READ.
        #
        # So the column has a floor set by its own longest row, in `ch` --
        # the width of a character in the font it is actually drawn in, so it
        # follows the reader's font rather than a guess in pixels. Capped at
        # 45% of the card, because a tree that swallows the window is a worse
        # lie than a narrow one. Where the window's true share is wider than
        # the floor, the true share still wins.
        tree_ch = max((len(re.sub(r"<[^>]+>", "", l)) for l in lines), default=0)
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
        placed = (not behind and getattr(st, "shape", None))
        pad = getattr(st, "_doc_pad", 0) if placed else 0
        wide = getattr(st, "_doc_wide", 0)
        blocks = getattr(st, "_doc_blocks", None) if placed else None
        bits = ([f"padding-top:{pad}px"] if pad else []) + \
               ([f"--sn-line:{wide}%"] if wide and wide < 98 else []) + \
               (["position:relative"] if blocks else [])
        sty_doc = f' style="{";".join(bits)}"' if bits else ""
        cols.append(f'<div class="sn-doc"{sty_doc}>'
                    + note_html(st, doc, title, blocks, wide) + "</div>")
    # THE PANES ARE AS WIDE AS THE SCREEN HAD THEM. The explorer and the
    # note share the window in the proportion the reader measured - the
    # tree's pane against the rest of the window - not a fixed 38 to 62,
    # which drew the explorer two and a half times too wide and squeezed
    # the note into a column a third of its real width.
    # THE FLOOR TRAVELS AS A VARIABLE, AND ONLY A CARD SETS IT. A picture must
    # stand at the shape the frame had: forcing this floor there widened the
    # tree past its true column and cost ten of seventeen pictures agreement
    # (mean 0.5159 -> 0.5047), which is the picture being made to lie so the
    # card could be read. `card_shot` sets `--sn-tree-min` on cards only; a
    # picture never sets it and falls back to the 120px it always had.
    if tree_ch:
        st._tree_min = "min(%dch, 45%%)" % min(44, tree_ch + 2)
    tree_floor = "var(--sn-tree-min, 120px)"
    tree_fr, doc_fr = 38, 62
    tp = next((q for q in getattr(st, "parts", []) if q.get("fam") == "tree" and q.get("x0") is not None), None)
    rect = getattr(st, "shape", None) or getattr(st, "rect", None)
    if tree and doc and tp and rect and rect[2] > tp["x1"] > tp["x0"] >= rect[0] - 4:
        tree_fr = max(8, round(100.0 * (tp["x1"] - tp["x0"]) / max(1.0, rect[2] - rect[0])))
        doc_fr = 100 - tree_fr
    # THE TREE NARROWS; NOTHING ELSE MOVES. Setting the note's column from
    # its own measured pane as well was tried and cost all three filled
    # pictures a fifth of their agreement: the drawn window has two columns
    # where the real one has five, so any width given to the note is width
    # its text spreads into, away from the narrow column the screen ran it
    # in. What the frame states plainly is how wide the TREE was, and the
    # room it does not use goes to a blank column between them -- so the
    # note's column stays exactly where it already lands and only the tree
    # stops being drawn four times too wide.
    measured_tree = getattr(st, "_tree_fr", 0) if (not behind and getattr(st, "shape", None)) else 0
    if measured_tree and tree and doc and measured_tree < tree_fr:
        gap = tree_fr - measured_tree
        grid = f"30px minmax({tree_floor}, {measured_tree}fr) {gap}fr {doc_fr}fr"
        cols.insert(len(cols) - 1, '<div class="sn-blank"></div>')
    else:
        grid = "30px " + (f"minmax({tree_floor}, {tree_fr}fr) " if tree else "") + (f"{doc_fr}fr" if doc else "")
    body = f'<div class="sn-cols sn-obsidian-cols" style="grid-template-columns: {grid.strip()}">' + "".join(cols) + "</div>"
    cls = "sn-window sn-obsidian" + (" sn-dark" if st.theme == "dark" else "")
    return f'<div class="{cls}">{strip}{toolbar}{body}</div>'


def note_html(st, doc, title, blocks=None, wide=0):
    """The note as Obsidian shows it: the tab's header line, the inline
    title, the properties block, then the body in its measured sizes.

    `blocks`, in a desktop picture only: the note's lines grouped by the
    pane they were read from, each later group with the height its pane
    stood at in the window's own unit. Those groups are placed THERE
    rather than flowed, so the text under a window in front lands where
    the screen had it and the room that window hid stays empty -- which is
    what the screen showed, since the window in front is drawn over it."""
    out = []
    at = {}
    if blocks:
        for bi, (top_u, texts) in enumerate(blocks):
            for t in texts:
                at.setdefault(plain_line_key(t), bi)
    groups = {}
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
        piece = bulleted(h)
        bi = at.get(plain_line_key(t), 0) if blocks else 0
        top_u = blocks[bi][0] if (blocks and bi < len(blocks)) else None
        if top_u is None:
            out.append(piece)
        else:
            groups.setdefault(bi, []).append(piece)
    # A NOTE SITS IN THE MIDDLE OF ITS PANE. Obsidian sets a note to a
    # readable line length and CENTRES that column; the style sheet's
    # `--sn-line` is a max-width, which left-aligns it. Measured on
    # 00:00:00, the frame runs the note from 0.448 to 0.714 of the screen
    # and the drawing ran it from 0.426 -- its lines reaching left into the
    # seam between the two Finder windows, a patch of screen that showed no
    # text at all. A block placed at its own height must carry the width and
    # the centring itself: once it is a block of its own, `--sn-line` no
    # longer reaches the lines inside it.
    # LEFT-ALIGNED, MEASURED. Centring the column was tried: Obsidian does
    # centre a note, but the drawn doc column is not the frame's pane, so
    # centring inside it put the note at 0.605-0.807 of the screen where the
    # frame has it at 0.448-0.714. Left-aligned it lands at 0.426, which is
    # the closest of the four placements measured. What is still short is
    # the column's WIDTH -- 0.203 of the screen against the frame's 0.266 --
    # and that comes from `_doc_wide` being borrowed from another moment.
    span = ("max-width:%d%%;" % wide if wide and wide < 98 else "")
    for bi in sorted(groups):
        out.append('<div class="sn-docblock" style="position:absolute;left:0;right:0;'
                   'padding:0 calc(26 * var(--sn-u, 1px));%s'
                   'top:calc(%d * var(--sn-u, 1px))">%s</div>'
                   % (span, blocks[bi][0], "".join(groups[bi])))
    if st.covered:
        out.append('<span class="sn-covered">the camera picture covered this corner of the window</span>')
    return "".join(out)


def plain_line_key(t):
    """A line's text stripped of its markdown marks, for matching a drawn
    line back to the pane it was read from."""
    return re.sub(r"\s+", " ", t.strip().strip("#*>-\u2022 ").strip().lower())[:60]


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


def scaled(html, rect, W, kz=1.0, cls="sn-slot", extra="", step=0.0):
    """A window drawn so its text stands the height the frame gave it: the
    sheet's writing shrunk to the screen's, and the window's own layout
    spread over the width its rectangle really had."""
    wide = max(1.0, rect[2] - rect[0])
    if step:
        k = max(0.05, step / ROW_H)          # measured on this very frame
    else:
        k = max(0.05, kz * (UI_TXT / CSS_TXT))
    w_css = (CANVAS_W * wide / W) / k
    tall = w_css * (rect[3] - rect[1]) / wide
    # ONE STYLE ATTRIBUTE, NOT TWO. This injects the window's height into
    # the card's own opening tag, so anything the card wants to say about
    # its layout has to be said HERE or it lands in a second `style` the
    # browser ignores. A Finder is laid out as a column, which is what lets
    # its path bar stand at the window's foot the way Finder puts it, rather
    # than riding up under the last file whenever the list is short.
    lay = ";display:flex;flex-direction:column" if "sn-finder" in html[:120] else ""
    html = re.sub(r'^(<div class="sn-window[^"]*")',
                  r'\1 style="min-height:calc(%d * var(--sn-u, 1px))%s"'
                  % (max(0, round(tall)), lay), html, count=1)
    # THE WINDOW IS MEASURED AGAINST ITS OWN BOX, NOT AGAINST THE PAGE. The
    # card is laid out at the width the rectangle really had, and one unit
    # of that layout is the box's width over that width - so the whole
    # window, type and padding and rows together, stands in the same
    # proportion to its box whatever width the reading pane gives the
    # picture. Drawn instead at a fixed pixel width and shrunk by a number
    # worked out for a 960-pixel page, everything inside sat a third too
    # large in a narrower pane, spilled past the window's edges and was cut
    # off there - which is content the screen showed and the picture lost.
    return (f'<div class="{cls}" style="{extra}">'
            f'<div class="sn-shot" style="--sn-u:calc(100cqw / {w_css:.0f})">'
            f'{html}</div></div>')


APPS = ("finder", "obsidian", "browser", "terminal", "chat")


def _app_of(tag):
    """The program a label names, or None where it names none."""
    t = (tag or "").lower()
    for a in APPS:
        if a in t:
            return a
    return None


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


def _glue(parts):
    """Pieces of one line put back together: a piece that begins mid-word is
    the tail of the piece before it. The address bar comes back as "AskGod"
    and "gle or type a URL" when the reader's cut falls inside a word."""
    out = []
    for t in parts:
        t = t.strip()
        if not t:
            continue
        if out and (t[:1].islower() or out[-1][-1:].islower() and len(t) < 4):
            out[-1] = out[-1] + t
        else:
            out.append(t)
    return " ".join(out)


def screen_shot(span, subjects, W, H, bar_words, clock, behind_cards=(),
                ghosts=(), camera=None, sure=True, kz=1.0, ink=(), chrome=(),
                chrome_step=0.0):
    """The layout of the screen over one stretch of time: the desktop bar
    with its own words, the window this stretch is about filled in with
    what it really said, and every other window standing where it stood,
    at the shape it had, drawn as a labelled outline. No picture is ever
    pasted in -- where the camera lay, an outline says so."""
    barred = bar_words is not None
    out = [f'<div class="sn-screen" style="aspect-ratio:{W} / {H}">']
    # THE SCREEN'S OWN INK, WHERE IT STOOD. A window the frame drew no
    # rectangle around - a browser filling the screen, a note behind
    # everything - was read and then thrown away, because only what stood
    # inside a measured rectangle was ever drawn. The picture then showed
    # two windows floating on black where the screen was full of words. So
    # every reading no filled window claims is laid back down at its own
    # place, in type the height it was measured at. It sits under
    # everything: an outline, a filled window and the bar all cover it, the
    # way they covered it on the screen.
    for x0, y0, x1, y1, text in ink or ():
        if not text:
            continue
        # what was MEASURED is the height of the ink; what CSS is told is
        # the size of the type, and a font's ink stands about seven tenths
        # of its own em. Setting the one as the other drew every word a
        # third small.
        high = max(1.0, float(y1) - float(y0)) / 0.72
        out.append(
            '<div class="sn-ink" style="left:%.2f%%;top:%.2f%%;'
            'font-size:calc(%.3fcqh)">%s</div>'
            % (100.0 * float(x0) / W, 100.0 * float(y0) / H,
               100.0 * high / H, esc(text)))
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
        if max((_within(box, r) for r in solid), default=0.0) < 0.85:
            return True
        # A WINDOW WHOSE OWN TOP STANDS ABOVE EVERY WINDOW IN FRONT OF IT IS
        # STILL ON THE SCREEN -- the strip of it above them is exactly what
        # shows. A browser standing behind a near-full-screen window is
        # covered by 95% of itself and its tabs are plainly there; measured
        # by share alone it counted as covered whole and its outline
        # vanished from the picture the moment its real box was measured.
        return bool(solid) and all(box[1] < r[1] - 0.005 * H for r in solid)

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
            # Two windows of DIFFERENT programs are two windows however
            # much ground they share - a note standing behind a file list
            # is not the same window as the list. Only a tag that names no
            # program at all folds into one that does.
            # A LABEL NAMES ITS PROGRAM WHATEVER ELSE IT SAYS AROUND IT.
            # Matching the whole label against a list of bare program names
            # let "the browser, behind" match nothing, so the guard did not
            # fire for it -- harmless while the browser was drawn as a thin
            # strip and not once its real box was measured, because the
            # browser and Obsidian then overlap by 0.94 and one would have
            # swallowed the other.
            named = [_app_of(t) for t in (tag, other[1])]
            if all(named) and named[0] != named[1]:
                continue
            share = max(_within(box, other[0]), _within(other[0], box))
            # `same` folds a stretch that could only say "Finder" into the
            # one that named its folder - two readings of ONE window, so
            # they stand at a like size. A small box inside a big one of
            # the same program is a window in FRONT of it: a note filling
            # the screen holds every other Obsidian window's rectangle, and
            # swallowing them loses the windows that were really there.
            if (like and (share > 0.85 or _close(box, other[0]))) or (same and like and share > 0.5):
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
        # A window drawn narrower than a finger's width holds nothing a
        # reader could read, and filling it in says the screen showed a
        # window there at a size it never had. Where the box came out that
        # small, what is honestly known is that a window stood there.
        thin = (rect[2] - rect[0] < 0.15 * W or rect[3] - rect[1] < 0.12 * H)
        st.shape = rect
        html = None if thin else (window(st, behind=False) or st.plain_window_html())
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
                          extra=f'{slot_style(rect, W, H, bar=barred)};z-index:{3 + z}',
                          step=getattr(st, "_row_step", 0.0)))
    # THE ONE WINDOW THAT MAY SHOW ITS CONTENT FROM BEHIND. Tristan's
    # exception, in his own words: "if a screen never shows up at all and
    # only part of the screen (like browser did with obsidian) than that can
    # be but behind whatever window in the desktop view with all of it's
    # content". The browser never stands clear anywhere in this video -- it
    # has no card of its own to hold its tabs and its address bar -- so the
    # strip of it that WAS in view is drawn where it stood, above the
    # outlines and under the windows in front, which is the order the screen
    # had. Everything else behind stays an outline.
    for cbox_, tabs_, addr_, right_ in chrome or ():
        if not (tabs_ or addr_):
            continue
        bits = ['<div class="sn-window sn-dark"><div class="sn-browser">']
        if tabs_:
            bits.append('<div class="sn-tabs">' + "".join(
                '<span class="sn-tab%s">%s</span>'
                % (" active" if re.sub(r"\W", "", t).lower() in ("newtab", "tab") else "",
                   esc(re.sub(r"\s*[xX\u00d7]$", "", t).strip()))
                for _, t in tabs_ if t.strip())
                + '<span class="sn-plus">+</span>'
                + "".join('<span class="sn-right">%s</span>' % esc(t)
                          for t in right_ if "emini" in t) + "</div>")
        if addr_:
            bits.append('<div class="sn-toolbar sn-address">'
                        '<span class="sn-btn">\u2039</span><span class="sn-btn">\u203a</span>'
                        '<span class="sn-btn">\u21bb</span>'
                        + '<span class="sn-urlbar">' + esc(_glue(addr_)) + "</span>"
                        + "".join('<span class="sn-btn sn-right">%s</span>' % esc(t)
                                  for t in right_ if "emini" not in t) + "</div>")
        bits.append("</div></div>")
        box = clip_box(cbox_, W, H, bar=barred)
        # POSITION IT EXPLICITLY. `sn-slot` and `sn-ghost` are placed by the
        # style sheet; `sn-behind` is a new class the sheet has never heard
        # of, so left/top/width/height did nothing at all and the whole
        # strip flowed to the top of the picture, across the desktop bar.
        # A picture must not depend on a snippet that has not caught up.
        out.append(scaled("".join(bits), box, W, kz=kz, cls="sn-behind",
                          step=chrome_step,
                          extra=("position:absolute;overflow:hidden;"
                                 + slot_style(box, W, H, bar=barred)
                                 + ";z-index:2")))
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


