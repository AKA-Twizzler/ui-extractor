"""The note, drawn as the windows the screen showed, with their content inside.

    python draw2.py <records.jsonl> [<note.md>]

One section per moment; inside it one callout per window, holding what
the window held: the sidebar as a line, the table rebuilt from where the
words sat (rows by height, columns by the header's positions, the
reader's leftovers put back in their cells), a tree as a code block, a
note as its own markdown, the path bar as a line. Markdown wherever
markdown can show it; HTML only for what markdown cannot draw (a colour,
an icon). A moment whose panes all read the same as an earlier one is
one line pointing back. No map, no dump of words under the window; the
doubt is one small line. The moment-by-moment record rides folded at
the end, so nothing the reader said is lost.
"""
import html
import json
import os
import re
import sys

import difflib

import draw as old   # the helpers that do not change: app names, clocks, the loose split

SCALE = 3                # the enlargement the structural readers measured in
LONG_SAID = 700          # Jared's words fold past this many characters
MAX_DOUBT = 14           # doubts named in the small line before "and N more"


# ------------------------------------------------------------- small helpers

def cell(s):
    """Text fit for a markdown table cell."""
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s.replace("|", "\\|")


def crumb_like(c):
    c = c.rstrip(">").strip()
    return (len(c) <= 28 and "'" not in c
            and (" " not in c or (c.count(" ") == 1 and c[:1].isupper())))


def reading_order(items, box_of):
    """Rows top to bottom, left to right within a row; two boxes share a
    row when their centres sit within half a box height of each other."""
    items = sorted(items, key=lambda it: ((box_of(it)[1] + box_of(it)[3]) / 2, box_of(it)[0]))
    rows, cur, cy = [], [], None
    for it in items:
        b = box_of(it)
        c = (b[1] + b[3]) / 2
        h = max(1, b[3] - b[1])
        if cy is not None and c - cy > 0.5 * h:
            rows.append(cur)
            cur, cy = [], None
        cur.append(it)
        if cy is None:
            cy = c
    if cur:
        rows.append(cur)
    return [sorted(r, key=lambda it: box_of(it)[0]) for r in rows]


def strip_note(line):
    """A document line without the reader's doubt suffix; the suffix is
    returned separately for the small line."""
    parts = re.split(r"\s+<- ", line.rstrip())
    return parts[0], [p.strip() for p in parts[1:]]


# ------------------------------------------------------------- what a pane holds

def items_of(pane):
    """Every reading on a pane as a dict: text, box in frame pixels, ok,
    role (head / cell / left / loose) and what the reader knew about it."""
    ox, oy = pane["box"][0], pane["box"][1]
    d = pane.get("data") or {}
    kind = pane["kind"]
    out = []

    def put(text, box, ok=True, role="loose", **extra):
        text = re.sub(r"\s+", " ", str(text)).strip()
        if not text:
            return
        it = {"text": text, "box": [float(v) for v in box], "ok": bool(ok), "role": role}
        it.update(extra)
        out.append(it)

    if kind == "text, not a tree":
        for r in d.get("readings") or []:
            b = r.get("box")
            if not b:
                continue
            put(r["text"], [b[0] / SCALE + ox, b[1] / SCALE + oy, b[2] / SCALE + ox, b[3] / SCALE + oy],
                ok=r.get("confirmed", True), role="loose", hue=r.get("hue"), icon=r.get("icon"),
                large=r.get("large"))
    elif kind == "a list of columns":
        for bi, blk in enumerate(d.get("blocks") or []):
            bands = [[v / SCALE + ox for v in band] for band in (blk.get("bands") or [])]
            hb = blk.get("head_box")
            header = blk.get("header") or []
            headflags = blk.get("headflags") or [None] * len(header)
            if hb:
                hy0, hy1 = hb[1] / SCALE + oy, hb[3] / SCALE + oy
                for i, h in enumerate(header):
                    if i < len(bands) and h:
                        put(h, [bands[i][0], hy0, bands[i][1], hy1], ok=not headflags[i], role="head", col=bands[i])
            flags = blk.get("flags") or []
            styles = blk.get("row_style") or []
            for ri, row in enumerate(blk.get("rows") or []):
                rb = (blk.get("row_boxes") or [None] * len(blk["rows"]))[ri]
                if not rb:
                    continue
                y0, y1 = rb[1] / SCALE + oy, rb[3] / SCALE + oy
                st = styles[ri] if ri < len(styles) and isinstance(styles[ri], dict) else {}
                fl = flags[ri] if ri < len(flags) else [None] * len(row)
                for i, c in enumerate(row):
                    if i < len(bands) and c:
                        put(c, [bands[i][0], y0, bands[i][1], y1], ok=not (fl[i] if i < len(fl) else None),
                            role="cell", col=bands[i], icon=st.get("icon") if i == 0 else None,
                            band=st.get("band"))
        for r in d.get("remainder") or []:
            b = r.get("box")
            if b:
                put(r["text"], [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], ok=r.get("confirmed", False), role="left")
    elif kind == "a file tree":
        for r in d.get("rows") or []:
            put(r.get("name") or r.get("raw") or "", [r["x0"] + ox, r["y0"] + oy, r["x1"] + ox, r["y1"] + oy],
                ok=r.get("name_status") != "uncertain", role="tree", depth=r.get("depth", 0),
                chevron=r.get("chevron"), kind=r.get("kind"))
        for r in d.get("remainder") or []:
            b = r.get("box")
            if b:
                put(r["text"], [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], ok=r.get("confirmed", False), role="left")
    elif kind == "an open document":
        for r in d.get("remainder") or []:
            b = r.get("box")
            if b:
                put(r["text"], [b[0] + ox, b[1] + oy, b[2] + ox, b[3] + oy], ok=r.get("confirmed", False), role="left")
    return out


def tree_band(pane):
    d = pane.get("data") or {}
    rows = d.get("rows") or []
    if not rows:
        return None
    oy = pane["box"][1]
    return (min(r["y0"] for r in rows) + oy, max(r["y1"] for r in rows) + oy)


# ------------------------------------------------------------- the table, rebuilt

def merge_columns(ranges, tol):
    """Column x-ranges clustered by where they start: two bands are one
    column when their left edges sit within `tol` of each other. Touching
    bands are neighbours, never one column."""
    cols = []
    for r in sorted(ranges, key=lambda r: r[0]):
        if cols and abs(r[0] - cols[-1][0]) <= tol:
            cols[-1] = [min(cols[-1][0], r[0]), max(cols[-1][1], r[1])]
        else:
            cols.append([r[0], r[1]])
    return cols


def table_rows(cells, rh):
    """Cells grouped into rows by the table's own row height: a cell joins
    the row whose centre sits within half a row of its own."""
    cells = sorted(cells, key=lambda it: ((it["box"][1] + it["box"][3]) / 2, it["box"][0]))
    rows, cur, cy = [], [], None
    for it in cells:
        c = (it["box"][1] + it["box"][3]) / 2
        if cy is not None and c - cy > 0.55 * rh:
            rows.append(cur)
            cur, cy = [], None
        cur.append(it)
        cy = c if cy is None else (cy * (len(cur) - 1) + c) / len(cur)
    if cur:
        rows.append(cur)
    return rows


def build_table(pane):
    """The table as the screen showed it: rows by height, columns by the
    header's positions, and the reader's leftovers put back where they sat.

    Returns (top_items, side_items, header, rows, bottom_items, doubts);
    rows are lists of (cells, icon, band)."""
    items = items_of(pane)
    cells = [it for it in items if it["role"] in ("head", "cell")]
    left = [it for it in items if it["role"] == "left"]
    doubts = []
    if not cells:
        return None
    heights = sorted(it["box"][3] - it["box"][1] for it in cells)
    rh = heights[len(heights) // 2] or 20
    cols = merge_columns([it["col"] for it in cells], tol=1.5 * rh)
    x_lo, x_hi = cols[0][0], cols[-1][1]
    y_lo = min(it["box"][1] for it in cells)
    y_hi = max(it["box"][3] for it in cells)
    top, side, bottom, inside = [], [], [], []
    for it in left:
        cx = (it["box"][0] + it["box"][2]) / 2
        cy = (it["box"][1] + it["box"][3]) / 2
        if it["box"][2] <= x_lo - rh and cy >= y_lo - rh:
            side.append(it)
        elif it["box"][3] <= y_lo - 0.3 * rh:
            top.append(it)
        elif it["box"][1] >= y_hi + 0.3 * rh:
            bottom.append(it)
        else:
            inside.append(it)
    # a leftover inside the table's band joins a column by its x, or opens one
    for it in inside:
        cx = (it["box"][0] + it["box"][2]) / 2
        hit = next((c for c in cols if c[0] - rh <= cx <= c[1] + rh), None)
        if hit is None:
            hit = [it["box"][0], it["box"][2]]
            cols.append(hit)
            cols.sort(key=lambda c: c[0])
        it["col"] = hit
        it["role"] = "cell"
    cells = cells + inside
    rows = table_rows(cells, rh)
    # the header row is the one holding the reader's header cells
    header = None
    body = []
    for r in rows:
        if header is None and any(it["role"] == "head" for it in r):
            header = r
        else:
            body.append(r)
    def by_column(r):
        out = [""] * len(cols)
        icon = band = None
        for it in sorted(r, key=lambda it: it["box"][0]):
            cx = (it["box"][0] + it["box"][2]) / 2
            ci = min(range(len(cols)), key=lambda i: 0 if cols[i][0] - rh <= cx <= cols[i][1] + rh else abs(cx - (cols[i][0] + cols[i][1]) / 2))
            text = it["text"] if it["ok"] else f"*{it['text']}*"
            out[ci] = (out[ci] + " " + text).strip()
            icon = icon or it.get("icon")
            band = band or it.get("band")
        return out, icon, band
    head_cells = by_column(header)[0] if header else [""] * len(cols)
    body_rows = [by_column(r) for r in body]
    # a column with no heading and under two cells is a stray reading's
    # doing; its cells fold into the neighbour on the left (or right)
    keep = []
    for i in range(len(cols)):
        filled = sum(1 for cells_, _, _ in body_rows if cells_[i])
        if not head_cells[i] and filled < 2 and len(cols) > 1:
            j = i - 1 if i > 0 else i + 1
            for cells_, _, _ in body_rows:
                if cells_[i]:
                    cells_[j] = (cells_[j] + " " + cells_[i]).strip()
                    cells_[i] = ""
        else:
            keep.append(i)
    head_cells = [head_cells[i] for i in keep]
    body_rows = [([cells_[i] for i in keep], icon, band) for cells_, icon, band in body_rows]
    return top, side, head_cells, body_rows, bottom, doubts


# ------------------------------------------------------------- pane blocks, as markdown

ICON = {"green": '<span class="sn-ico"></span>', "grey": '<span class="sn-ico grey"></span>',
        "white": '<span class="sn-ico file"></span>'}


def md_table(head, rows):
    n = max([len(head)] + [len(r[0]) for r in rows]) if rows or head else 0
    if n == 0:
        return []
    head = list(head) + [""] * (n - len(head))
    out = ["| " + " | ".join(cell(h) for h in head) + " |",
           "|" + "---|" * n]
    for cells, icon, band in rows:
        cells = list(cells) + [""] * (n - len(cells))
        cells = [cell(c) for c in cells]
        if icon in ICON and cells and cells[0]:
            cells[0] = ICON[icon] + " " + cells[0]
        if band:
            cells = [f"**{c}**" if c else c for c in cells]
        out.append("| " + " | ".join(cells) + " |")
    return out


def words_line(items):
    """Loose items as lines of words in reading order."""
    return [" &nbsp; ".join(it["text"] for it in r) for r in reading_order(items, lambda it: it["box"])]


def block_list(pane):
    built = build_table(pane)
    lines, doubts = [], []
    if not built:
        return lines, doubts
    top, side, head, rows, bottom, doubts = built
    def say(it):
        return it["text"] if it["ok"] else f"*{it['text']}*"
    if top:
        lines.append("**Toolbar:** " + " · ".join(say(it) for it in sorted(top, key=lambda it: it["box"][0])))
    if side:
        lines.append("**Sidebar:** " + " · ".join(say(it) for it in sorted(side, key=lambda it: it["box"][1])))
    if top or side:
        lines.append("")
    lines.extend(md_table(head, rows))
    if bottom:
        items = sorted(bottom, key=lambda it: (round(it["box"][1] / 10), it["box"][0]))
        crumbs = [say(it).rstrip(">").strip() for it in items if crumb_like(it["text"])]
        words = [say(it) for it in items if not crumb_like(it["text"])]
        if len(crumbs) >= 2:
            lines.append("")
            lines.append("**Path:** " + " › ".join(crumbs))
        if words:
            lines.append("")
            lines.append(" · ".join(words))
    return lines, doubts


def block_tree(pane):
    d = pane.get("data") or {}
    rows = d.get("rows") or []
    lines, doubts = ["```text"], []
    for r in rows:
        ch = {"right": "▸ ", "down": "▾ "}.get(r.get("chevron"), "  ")
        name = r.get("name") or r.get("raw") or ""
        lines.append("  " * int(r.get("depth", 0)) + ch + name)
        if r.get("name_status") == "uncertain" and r.get("name_second"):
            doubts.append(f"{name} / {r['name_second']}")
    lines.append("```")
    if not rows:
        lines = []
    return lines, doubts


def block_document(pane):
    lines, doubts, props = [], [], []
    in_props = False
    for raw in pane.get("lines") or []:
        s = raw.strip()
        if s.startswith(("[also on this pane", "unsettled:", "[dark look", "[light look")):
            if s.startswith("unsettled:"):
                doubts.append(s[len("unsettled:"):].strip())
            continue
        text, notes = strip_note(raw)
        for n in notes:
            if n.startswith("drawn in ") and n[len("drawn in "):] in old.HUES:
                hue = n[len("drawn in "):]
                text = f'<span class="sn-{hue}">{text.strip()}</span>'
            elif n.startswith("the line runs on past the edge"):
                text = text.rstrip() + "…"
            else:
                doubts.append(f"{text.strip()[:30]}: {n}")
        if text.strip() == "---":
            if in_props:
                lines.append("**Properties:** " + " · ".join(props))
                lines.append("")
                props = []
            in_props = not in_props
            continue
        if in_props:
            props.append(text.strip())
            continue
        indent = len(text) - len(text.lstrip(" "))
        body = text.strip()
        if not body:
            continue
        pad = "&nbsp;" * min(8, indent)
        lines.append(pad + body if indent >= 4 and not body.startswith(("#", "-", "*")) else body)
    return lines, doubts


def block_lines(pane):
    """A terminal or chat: its lines in a code block."""
    lines = [ln for ln in old.content_lines(pane) if ln.strip()]
    return (["```text"] + [ln.rstrip() for ln in lines] + ["```"]) if lines else [], []


def block_loose(pane, window_rect):
    """Loose words: a narrow strip is a sidebar line, a short strip along the
    top a toolbar line, anything else lines of words in reading order."""
    items = [it for it in items_of(pane) if it["ok"]]
    doubts = [it["text"] for it in items_of(pane) if not it["ok"]]
    if not items:
        return [], doubts
    x0, y0, x1, y1 = pane["box"]
    W = max(1, window_rect[2] - window_rect[0])
    H = max(1, window_rect[3] - window_rect[1])
    w, h = x1 - x0, y1 - y0
    texts_in_order = [it["text"] for r in reading_order(items, lambda it: it["box"]) for it in r]
    if w < 0.3 * W and h > w:
        return ["**Sidebar:** " + " · ".join(texts_in_order)], doubts
    if h < 0.12 * H and y0 < window_rect[1] + 0.1 * H:
        return ["**Toolbar:** " + " · ".join(texts_in_order)], doubts
    return words_line(items), doubts


def block_of(pane, window_rect):
    k = pane["kind"]
    if k == "a list of columns":
        return block_list(pane)
    if k == "a file tree":
        return block_tree(pane)
    if k == "an open document":
        return block_document(pane)
    if k in ("a terminal", "a chat log"):
        return block_lines(pane)
    return block_loose(pane, window_rect)


# ------------------------------------------------------------- windows and moments

FINDER_HEADS = {"Name", "Date Modified", "Size", "Kind", "Date Created", "Date Added"}


def name_of(entry, panes):
    """The program, from its furniture; a list under Finder's own column
    headings is Finder even with its sidebar out of view."""
    app = old.app_name(entry, panes)
    if not app:
        for p in panes:
            if p["kind"] == "a list of columns":
                heads = {h for b in (p.get("data") or {}).get("blocks") or [] for h in (b.get("header") or [])}
                if len(heads & FINDER_HEADS) >= 2:
                    app = "Finder"
    return (app[0].upper() + app[1:]) if app else None


def touching(a, b, W):
    """Two pane boxes that share an edge, left-right or top-bottom."""
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    gap = 0.02 * W
    side = (abs(ax1 - bx0) < gap or abs(bx1 - ax0) < gap) and min(ay1, by1) - max(ay0, by0) > 0
    stack = (abs(ay1 - by0) < gap or abs(by1 - ay0) < gap) and min(ax1, bx1) - max(ax0, bx0) > 0
    return side or stack


def window_groups(m):
    """The windows of a moment: (name, rect, panes). Panes on no found
    window form one group of their own."""
    wins = m.get("windows") or []
    groups = []
    for wi, e in enumerate(wins):
        panes = [p for p in m["panes"] if p.get("wi") == wi]
        if not panes:
            continue
        name = name_of(e, panes) or "A window"
        title = e.get("top")
        groups.append({"name": name, "title": title, "rect": e["rect"], "panes": panes, "where": e.get("where")})
    rest = [p for p in m["panes"] if p.get("wi") is None or p.get("wi") >= len(wins)]
    size = list(m.get("size") or [1920, 1080])
    if rest and groups:
        groups.append({"name": "The rest of the screen", "title": None, "rect": [0, 0] + size,
                       "panes": rest, "where": None})
    elif rest:
        # no window was found: each structural pane is a window of its own,
        # with any narrow loose strip beside it as its sidebar; loose panes
        # left over stand alone
        W = size[0]
        structural = [p for p in rest if p["kind"] in old.STRUCTURAL]
        loose = [p for p in rest if p["kind"] not in old.STRUCTURAL]
        taken = set()
        # panes that touch, directly or through a narrow strip between them,
        # are one window (a tree, the panel beside it, and the note)
        def narrow(p):
            return (p["box"][2] - p["box"][0]) < 0.3 * W
        clusters = []
        for sp in sorted(structural, key=lambda p: p["box"][0]):
            members = [sp]
            grew = True
            while grew:
                grew = False
                for q in rest:
                    if q is sp or id(q) in taken or q in members:
                        continue
                    if q["kind"] not in old.STRUCTURAL and not narrow(q):
                        continue
                    if any(touching(q["box"], r["box"], W) for r in members):
                        members.append(q)
                        grew = True
            # a structural pane already claimed by an earlier cluster means
            # this one joined it through the chain; fold them together
            home = next((c for c in clusters if any(r in c for r in members)), None)
            if home is not None:
                for r in members:
                    if r not in home:
                        home.append(r)
                continue
            clusters.append(members)
        for members in clusters:
            sp = members[0]
            for q in members:
                taken.add(id(q))
            e = {"rect": [0, 0] + size, "top": None}
            name = name_of(e, members) or f"A window, {sp.get('where') or 'on the screen'}"
            x0 = min(p["box"][0] for p in members); x1 = max(p["box"][2] for p in members)
            y0 = min(p["box"][1] for p in members); y1 = max(p["box"][3] for p in members)
            groups.append({"name": name, "title": None, "rect": [x0, y0, x1, y1], "panes": members, "where": sp.get("where")})
        for lp in loose:
            if id(lp) in taken or any(lp in c for c in clusters):
                continue
            e = {"rect": [0, 0] + size, "top": None}
            name = name_of(e, [lp]) or f"Loose words, {lp.get('where') or 'on the screen'}"
            groups.append({"name": name, "title": None, "rect": lp["box"], "panes": [lp], "where": lp.get("where")})
    groups.sort(key=lambda g: g["rect"][0])
    return groups


def draw_group(g):
    """One callout: the window's name as its title, its content inside."""
    rect = g["rect"]
    title = g["name"] + (f" - {g['title']}" if g.get("title") else "")
    body, doubts, repeats = [], [], []
    panes = sorted(g["panes"], key=lambda p: (p["box"][0], p["box"][1]))
    for p in panes:
        if p.get("since"):
            repeats.append(f"{p.get('where') or 'a pane'}: unchanged since {p['since']}")
            continue
        if p.get("same_as"):
            repeats.append(f"{p.get('where') or 'a pane'}: the same as at {p['same_as']}")
            continue
        lines, d = block_of(p, rect)
        doubts.extend(d)
        if lines:
            if body:
                body.append("")
            body.extend(lines)
    for r in repeats:
        body.append("")
        body.append(f"*{r}*")
    if not body:
        return [], doubts
    out = [f"> [!window] {title}"]
    for ln in body:
        out.append("> " + ln if ln else ">")
    return out, doubts


def said_lines(m):
    said = (m.get("said") or "").strip()
    if not said:
        return []
    if len(said) > LONG_SAID:
        return [f"> [!quote]- Jared, {m['ts']} ({len(said.split())} words)", "> " + said]
    return [f'Jared, {m["ts"]}: "{said}"']


SAME = 0.9


def flat(lines):
    text = re.sub(r"&[a-z]+;|<[^>]+>", " ", " ".join(lines))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def alike(a, b):
    """1.0 when every line of one drawing has a near twin in the other (a
    letter wobble is a twin; a new line or a vanished one is not)."""
    def norm(lines):
        return [flat([ln]) for ln in lines if flat([ln])]
    A, B = norm(a), norm(b)
    if not A or not B:
        return 0.0
    def covered(xs, ys):
        scraps = 0
        for x in xs:
            best = max((difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() for y in ys
                        if abs(len(x) - len(y)) <= max(4, 0.3 * len(x))), default=0.0)
            if best < 0.8:
                # a short scrap with no twin is the engines' noise; a real
                # line with no twin is a change on the screen
                if len(x) < 16 and scraps < 2:
                    scraps += 1
                    continue
                return False
        return True
    return 1.0 if covered(A, B) and covered(B, A) else 0.0


def group_key(g, W):
    """A window's identity across moments: its name and where it stands."""
    return f"{g['name']}@{int(8 * g['rect'][0] / max(1, W))}"


def draw_moment(m, prev_clock, prev_groups=None):
    groups = window_groups(m)
    names = " · ".join(g["name"] + (f" ({g['title']})" if g.get("title") else "") for g in groups)
    all_repeat = all(p.get("since") or p.get("same_as") for p in m["panes"]) and m["panes"]
    clock = None
    for p in m["panes"]:
        c = old.clock_in(p)
        if c:
            clock = c
    head = f"## {m['ts']} - {names or 'nothing readable'}"
    if all_repeat:
        since = sorted({p.get("since") or p.get("same_as") for p in m["panes"]})
        out = [head + f" - the same screen as at {', '.join(since)}"]
        out.extend(said_lines(m))
        return out, clock, prev_groups
    out = [head]
    doubts = []
    drawn = {}
    W = (m.get("size") or [1920])[0]
    for g in groups:
        lines, d = draw_group(g)
        g["ts"] = m["ts"]
        key = group_key(g, W)
        drawn[key] = (lines, g)
        # the same window drawn the same way a moment ago: one line back
        before = (prev_groups or {}).get(key)
        if before and lines and before[0] and alike(lines, before[0]) >= SAME:
            drawn[key] = before      # the earlier drawing stands as the reference
            out.append("")
            out.append(f"> [!window] {g['name']} - the same as at {before[1].get('ts', '?')}")
            continue
        doubts.extend(d)
        if lines:
            out.append("")
            out.extend(lines)
    out.append("")
    out.extend(said_lines(m))
    small = []
    if clock and clock != prev_clock:
        small.append(f"the clock reads {clock}")
    if doubts:
        seen, kept = set(), []
        for d in doubts:
            d = re.sub(r"\s+", " ", d).strip()
            if d and d not in seen:
                seen.add(d)
                kept.append(d)
        more = f" and {len(kept) - MAX_DOUBT} more" if len(kept) > MAX_DOUBT else ""
        small.append("doubt: " + " · ".join(html.escape(x, quote=False) for x in kept[:MAX_DOUBT]) + more)
    if small:
        out.append("")
        out.append("<small>" + "; ".join(small) + "</small>")
    return out, clock, drawn


def note(records_path, diary_text=None):
    header, moments, footer = old.load(records_path)
    title = header.get("title") or os.path.basename(os.path.dirname(records_path))
    diary_text = diary_text if diary_text is not None else old.diary(records_path)
    secs = (moments[-1]["secs"] - moments[0]["secs"]) if len(moments) > 1 else 0
    apps = []
    for m in moments:
        for g in window_groups(m):
            n = g["name"]
            if n not in apps and n not in ("The screen", "The rest of the screen", "A window"):
                apps.append(n)
    clocks = [c for m in moments for p in m.get("panes") or [] for c in [old.clock_in(p)] if c]
    parts = [f"# {title}", ""]
    head = f"A screen recording, {old.minutes(secs)} read, {len(moments)} screen moments in order."
    if apps:
        head += " On screen: " + "; ".join(apps) + "."
    if clocks:
        head += f" The desktop clock read {clocks[0]}" + (f" at the start and {clocks[-1]} at the end." if clocks[-1] != clocks[0] else ".")
    parts.append(head)
    parts.append("")
    prev_clock = None
    prev_groups = {}
    for m in moments:
        lines, clock, prev_groups = draw_moment(m, prev_clock, prev_groups)
        prev_clock = clock or prev_clock
        parts.extend(lines)
        parts.append("")
    n = len(moments)
    parts.append(f"> [!note]- The moment-by-moment record, {n} moments (appendix)")
    parts.append("> ````text")
    for ln in diary_text.rstrip("\n").split("\n"):
        parts.append("> " + ln if ln else ">")
    parts.append("> ````")
    return "\n".join(parts) + "\n"


def main():
    records = sys.argv[1]
    text = note(records)
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
    raise SystemExit(main())
