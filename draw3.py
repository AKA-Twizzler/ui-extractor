"""The note, drawn as window states: each window as the screen showed it,
its content inside, on the vault's style sheet.

    python draw3.py <records.jsonl> [<note.md>]

The shape Tristan approved: the window on the style sheet (sidebar beside
the list, tree beside the open note), content inside, Jared's words under
it, the doubt as fine print. One section per window STATE: a state is a
window showing one thing (one folder, one note); a later moment showing
the same thing extends the drawing (a scrolled tree or note grows, a list
gains its rows) instead of opening a new section. A new section comes
only when the window shows something else. Earlier states of the same
window are listed under each. No map; nothing of the screen is said
outside its window except Jared's words and the fine print. The desktop
(menu bar, clock) once at the end; the moment-by-moment record folded as
the appendix.
"""
import difflib
import html
import os
import re
import sys

import draw as old          # HTML line helpers that do not change
import draw2                # the geometry: items, tables rebuilt, window groups

LONG_SAID = 700
MAX_DOUBT = 12
STITCH_MIN = 0.8            # a row or line is "the same" at this ratio


def esc(s):
    return html.escape(str(s), quote=False)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


# ------------------------------------------------------------- content models
#
# Every pane kind reduces to one of three content shapes, merged across the
# moments of a state:
#   table: header (list of str), rows (list of dict: cells, band, ok flags)
#   lines: list of (text, marks) for a tree or a document
#   words: list of str, for a loose strip

def same_text(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or (len(a) >= 8 and (a in b or b in a)):
        return True
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= STITCH_MIN


def plain_line(t):
    return norm(t.strip().strip("#*> ").strip())


def same_doc_line(a, b):
    """The same line of a note: alike, or one holding the other whole (the
    note re-wrapped to a wider window), or most letters in common."""
    if a.startswith("---") or b.startswith("---"):
        return norm(a) == norm(b)
    if same_line(a, b):
        return True
    x, y = plain_line(a), plain_line(b)
    if len(x) >= 12 and len(y) >= 12 and (x in y or y in x):
        return True
    xs, ys = re.sub(r"[0-9]{0,2}$", "", x), re.sub(r"[0-9]{0,2}$", "", y)
    if len(xs) >= 12 and len(ys) >= 12 and (xs in y or ys in x):
        return True                 # the same line with a scrap on its end
    return len(x) >= 12 and len(y) >= 12 and difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.7


def same_line(a, b):
    """Two lines of a note are the same line when they read nearly alike;
    a line that merely begins another is not it."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    if long_.startswith(short) and len(short) >= 0.7 * len(long_):
        return True
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.85


def same_name(a, b):
    """Two readings of one file name: alike, or the same length with at
    most two letters read differently (0olnbox / ooInbox)."""
    if same_text(a, b):
        return True
    a, b = norm(a), norm(b)
    return bool(a) and len(a) == len(b) and len(a) <= 12 and sum(1 for x, y in zip(a, b) if x != y) <= 2


def stitch(old_items, new_items, key, same=same_text, merge=None):
    """Extend `old_items` with what `new_items` adds, in place: find where
    the new run overlaps the old (by `key` likeness) and append what lies
    past the overlap; rows the old run lacks inside the overlap are put
    where they sat. With no overlap at all the new run is appended whole."""
    if not old_items:
        return list(new_items)
    if not new_items:
        return old_items
    # the longest matching stretch: for each new item find the old twin
    pairs = []
    out = list(old_items)
    for j, n in enumerate(new_items):
        for i, o in enumerate(old_items):
            if same(key(o), key(n)):
                pairs.append((i, j))
                if merge is not None:
                    out[i] = merge(o, n)
                break
    if not pairs:
        return old_items + list(new_items)
    # walk the new run; unmatched items go after their nearest matched
    # predecessor's twin, and those before the first twin go just before it
    matched = {j: i for i, j in pairs}      # new index -> old index
    first_old = matched[min(matched)]
    last_old = first_old - 1
    insert_at = {}
    for j, n in enumerate(new_items):
        if j in matched:
            last_old = matched[j]
            continue
        insert_at.setdefault(last_old, []).append(n)
    result = []
    for i, o in enumerate(out):
        if i == 0 and -1 in insert_at:
            result.extend(insert_at[-1])
        result.append(o)
        if i in insert_at:
            result.extend(insert_at[i])
    if not out and -1 in insert_at:
        result.extend(insert_at[-1])
    return result


MONTHS3 = {m.lower(): m for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]}
DATE_RX = re.compile(r"^\s*(?:(Today|Yesterday|today|yesterday)|([A-Za-z]{3})\s*(\d{1,2})\s*[,.]?\s*(\d{4}))"
                     r"\s*at\s*(\d{1,2})\s*[:.°º*/]?\s*(\d{2})\s*([AaPp])\s*[Mm]\s*$")
SIZE_RX = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(bytes?|[KMGT]B)\b\s*N?\s*(.*)$", re.I)


def tidy_date(s):
    """A Finder date rebuilt to the shape the screen drew it in, or None:
    'Jun30,2026at5:51PM' -> 'Jun 30, 2026 at 5:51 PM'."""
    m = DATE_RX.match(s.replace("*", ""))
    if not m:
        return None
    if m.group(2):
        mon = MONTHS3.get(m.group(2).lower())
        if not mon:
            return None
        day = f"{mon} {int(m.group(3))}, {m.group(4)}"
    else:
        day = m.group(1).capitalize()
    return f"{day} at {int(m.group(5))}:{m.group(6)} {m.group(7).upper()}M"


def tidy_size(s):
    """A size leading a cell split from what follows it: '2KB Markdo...text
    file' -> ('2 KB', 'Markdo...text file'); None when no size leads."""
    m = SIZE_RX.match(s.replace("*", ""))
    if not m:
        return None
    unit = m.group(2)
    unit = "bytes" if unit.lower().startswith("byte") else unit.upper()
    return f"{m.group(1)} {unit}", m.group(3).strip()


class Table:
    def __init__(self):
        self.header = []
        self.rows = []          # each: {"cells": [...], "band": hue, "italic": [bool]}
        self.side = []
        self.top = []
        self.top_items = []     # (text, centre x) for the title rule
        self.span = None        # the list's x-span
        self.path = []
        self.paths = []         # every path bar read, latest last
        self.rh = 0.0           # a row's height in frame pixels
        self.bottom = []
        self.banded_names = set()

    STANDARD = {4: ["Name", "Date Modified", "Size", "Kind"], 3: ["Name", "Date Modified", "Kind"],
                2: ["Name", "Date Modified"], 5: ["Name", "Date Modified", "Size", "Kind", ""]}

    def add(self, built):
        top, side, head, rows, bottom = built[:5]
        head = list(head or [])
        # the reader takes the first file for the header when the real
        # headings scrolled off; a header with none of Finder's words and a
        # file-like first cell is a row, and the standard headings stand in
        if head and not any(h in FINDER_WORDS for h in head) and head[0] and (
                "." in head[0] or re.search(r"\d{4}", " ".join(head))):
            rows = [(head, None, None)] + list(rows)
            head = self.STANDARD.get(len(head), [""] * len(head))
        if head and not head[0] and sum(1 for h in head if h in FINDER_WORDS) >= 2 and "Name" not in head:
            head[0] = "Name"
        for i, h in enumerate(head):
            parts_ = draw2.split_heads(h)
            if len(parts_) >= 2:
                # two headings read as one: the column is the one its cells
                # belong to, told by what the cells hold
                col = [c for cells_, _, _ in rows if i < len(cells_) and cells_[i] for c in [cells_[i]]]
                def share(rx):
                    return sum(1 for c in col if re.search(rx, c)) * 2 >= max(1, len(col))
                if col and share(r"(Folder|Document|text file|JSON|Log File|Image|Application)"):
                    pick = "Kind"
                elif col and share(r"(\d{4}|Today|Yesterday)"):
                    pick = "Date Modified" if "Date Modified" in parts_ else parts_[0]
                elif col and share(r"\d+\s?(bytes|KB|MB|GB)"):
                    pick = "Size"
                else:
                    pick = parts_[0]
                head[i] = pick if pick in parts_ else parts_[0]
        for i, h in enumerate(head):
            if h and i < len(self.header) and not self.header[i] and not any(same_text(h, g) for g in self.header if g):
                self.header[i] = h
        # a later reading's columns map onto the first by heading name; a
        # column with no heading keeps its position; one the table lacks
        # is added at the end
        if not self.header or not any(self.header):
            self.header = head
        mapping = list(range(len(head)))
        if head and any(head) and self.header is not head:
            mapping = []
            for i, h in enumerate(head):
                j = next((k for k, g in enumerate(self.header) if h and g and same_text(h, g)), None)
                if j is None and not h and i < len(self.header) and not self.header[i]:
                    j = i
                if j is None and h:
                    # in at its own place: after the column the previous heading maps to
                    at = (mapping[-1] + 1) if mapping and mapping[-1] is not None else len(self.header)
                    at = min(at, len(self.header))
                    self.header.insert(at, h)
                    for r in self.rows:
                        r["cells"].insert(at, "")
                        r["italic"].insert(at, False)
                    mapping = [k + 1 if k is not None and k >= at else k for k in mapping]
                    j = at
                mapping.append(j if j is not None else i)
        new_rows = []
        if len(built) > 7 and built[7]:
            self.rh = max(self.rh, float(built[7]))
        for cells, icon, band in rows:
            width = max(len(self.header), max(mapping, default=-1) + 1, len(cells))
            plain = [""] * width
            italics = [False] * width
            for i, c in enumerate(cells):
                if not c:
                    continue
                j = mapping[i] if i < len(mapping) else i
                if j >= width:
                    continue
                it = c.startswith("*") and c.endswith("*") and len(c) > 2
                plain[j] = (plain[j] + " " + c.replace("*", "")).strip()
                italics[j] = italics[j] or it
            new_rows.append({"cells": plain, "italic": italics, "band": band, "icon": icon})
        def keep(o, n):
            # twins: the confirmed reading stands over the doubtful one,
            # and a cell the old row lacks is filled from the new
            if o["italic"] and o["italic"][0] and n["cells"] and n["cells"][0] and not (n["italic"] and n["italic"][0]):
                o = {"cells": [n["cells"][0]] + o["cells"][1:], "italic": [False] + o["italic"][1:], "band": o["band"] or n["band"], "icon": o.get("icon") or n.get("icon")}
            cells = list(o["cells"])
            italics = list(o["italic"])
            for i, c in enumerate(n["cells"]):
                if i < len(cells) and not cells[i] and c:
                    cells[i] = c
                    italics[i] = n["italic"][i] if i < len(n["italic"]) else False
            return {"cells": cells, "italic": italics, "band": o["band"] or n["band"], "icon": o.get("icon") or n.get("icon")}
        self.rows = stitch(self.rows, new_rows, key=lambda r: r["cells"][0] if r["cells"] else "", same=same_name, merge=keep)
        # a row whose name was missed folds into the row with the same
        # other cells; a nameless row alone is the window behind
        named = [r for r in self.rows if r["cells"] and r["cells"][0]]
        kept = []
        for r in self.rows:
            if r["cells"] and r["cells"][0]:
                name = r["cells"][0]
                if not any(r["cells"][1:]) and ((len(name) > 40 and name.count(" ") >= 5) or (len(name) > 45 and "." not in name)):
                    continue      # a sentence with no other cells: the window behind
                kept.append(r)
                continue
            rest = " ".join(r["cells"][1:]).strip()
            twin = next((n for n in named if rest and same_text(" ".join(n["cells"][1:]), rest)), None)
            if twin is None and rest and len(named) < 2:
                kept.append(r)
        self.rows = kept
        new_side = []
        for it in sorted(side, key=lambda it: it["box"][1]):
            t = it["text"].strip("*")
            full = next((w for w in draw2.SIDEBAR_WORDS if w != t and len(t) >= 4 and w.endswith(t)), None)
            if full:
                t = full
            elif t in draw2.SIDEBAR_WORDS:
                pass
            elif t.endswith((".", ",")) or t.count(" ") >= 2 or len(t) < 3 or (" " in t and t[:1].islower()):
                continue
            if not any(same_text(t, s) for s in new_side):
                new_side.append(t)
        self.side = stitch(self.side, new_side, key=lambda w: w)
        for it in sorted(top, key=lambda it: it["box"][0]):
            t = it["text"]
            if not any(same_text(t, s) for s in self.top):
                self.top.append(t)
                self.top_items.append((t, (it["box"][0] + it["box"][2]) / 2, it["ok"], it.get("above", 99)))
        rows_below = draw2.reading_order([it for it in bottom if it["ok"]], lambda it: it["box"])
        known = {norm(r["cells"][0]) for r in self.rows if r["cells"] and r["cells"][0]}
        known |= {norm(t) for t, _, _, _ in self.top_items if t}
        best = []
        for row in rows_below:
            # the path is the leading run of crumbs on a row; words after
            # it are the window behind showing through. A crumb that is the
            # list's own folder or a row's name continues the run whatever
            # its shape (the path bar names what the window shows).
            run = []
            for it in row:
                c = it["text"].rstrip(">").strip()
                if (draw2.crumb_like(it["text"]) or norm(c) in known) and not (run and norm(c) == norm(run[0])):
                    run.append(c)
                else:
                    break
            if len(run) >= 2 and len(run) > len(best):
                best = run
            for it in row[len(run):]:
                if it["text"] not in self.bottom:
                    self.bottom.append(it["text"])
        if len(best) >= len(self.path):
            self.path = best
        if best and best not in self.paths:
            self.paths.append(best)
        self.tidy()

    def tidy(self):
        """Cells put back the way Finder drew them: dates in Finder's date
        shape (a date that parses is its own confirmation), a size leading a
        Kind cell split out into the Size column -- the column added when the
        reader missed its heading."""
        hdr = self.header
        di = next((i for i, h in enumerate(hdr) if h == "Date Modified"), None)
        si = next((i for i, h in enumerate(hdr) if h == "Size"), None)
        ki = next((i for i, h in enumerate(hdr) if h == "Kind"), None)
        if si is None and ki is not None and any(
                ki < len(r["cells"]) and (lambda m: m and m[1])(tidy_size(r["cells"][ki])) for r in self.rows):
            si = ki
            hdr.insert(si, "Size")
            for r in self.rows:
                r["cells"].insert(si, "")
                r["italic"].insert(si, False)
            ki += 1
        for r in self.rows:
            cs, its = r["cells"], r["italic"]
            if di is not None and di < len(cs) and cs[di]:
                d = tidy_date(cs[di])
                if d:
                    cs[di], its[di] = d, False
            if ki is not None and ki < len(cs) and cs[ki]:
                m = tidy_size(cs[ki])
                if m:
                    size, rest = m
                    if si is not None and si < len(cs) and not cs[si]:
                        cs[si], cs[ki] = size, rest
                        its[ki] = its[ki] and bool(rest)
            if si is not None and si < len(cs) and cs[si]:
                m = tidy_size(cs[si])
                if m:
                    size, rest = m
                    cs[si] = size
                    its[si] = False
                    if rest and ki is not None and ki < len(cs) and not cs[ki]:
                        cs[ki] = rest

    def names(self):
        return [norm(r["cells"][0]) for r in self.rows if r["cells"] and r["cells"][0]]

    def identity(self):
        """What folder the list shows: its rows' names."""
        return " ".join(self.names())

    def html(self):
        n = max([len(self.header)] + [len(r["cells"]) for r in self.rows] + [0])
        out = ["<table>"]
        if self.header and any(self.header):
            out.append("<tr class=\"sn-head\">" + "".join(f"<td>{esc(h)}</td>" for h in list(self.header) + [""] * (n - len(self.header))) + "</tr>")
        for r in self.rows:
            cells = list(r["cells"]) + [""] * (n - len(r["cells"]))
            it = list(r["italic"]) + [False] * (n - len(r["italic"]))
            cls = ' class="sn-selected"' if r.get("band") else ""
            tds = "".join(f"<td>{'<i>' + esc(c) + '</i>' if it[i] and c else esc(c)}</td>" for i, c in enumerate(cells))
            out.append(f"<tr{cls}>{tds}</tr>")
        out.append("</table>")
        return "".join(out)


def doc_html(model):
    """The note as drawn: its title line large when the first line is short
    and sits above the properties; scraps without a letter left out."""
    lines = [(t, h) for t, h in model.lines if re.search(r"[A-Za-z0-9]", t)]
    out = []
    for i, (t, h) in enumerate(lines):
        plain = t.strip().strip("#*> ").strip()
        if i == 0 and len(plain) <= 40 and not t.startswith("---") and "<div class=\"sn-h" not in h:
            out.append(f'<div class="sn-title">{esc(plain)}</div>')
            continue
        out.append(h)
    return "".join(out)


def tree_depth(text):
    return len(text) - len(text.lstrip("│ "))


class Lines:
    """A tree or a document, as lines that grow when the pane scrolls."""
    def __init__(self, kind):
        self.kind = kind
        self.lines = []         # (text, html)
        self.doubt = set()      # texts one engine alone read

    def add(self, pairs):
        pairs = list(pairs)
        if self.kind == "an open document":
            # a note grows by its text: a line already there (the window
            # wider or narrower, the lines re-wrapped) is the same line, and
            # the longer reading of it stands
            def wordy(s):
                toks = re.findall(r"[A-Za-z][A-Za-z'’]*", s)
                if not toks:
                    return 0.0
                good = sum(1 for t in toks if re.search(r"[aeiouyAEIOUY]", t) and (len(t) <= 14 or "_" in s))
                return good / len(toks)

            def merge(o, n):
                lo, ln = len(norm(o[0])), len(norm(n[0]))
                od, nd = o[0] in self.doubt, n[0] in self.doubt
                if od != nd and abs(lo - ln) <= 8:
                    return n if od else o          # the reading both engines backed
                po, pn = plain_line(o[0]), plain_line(n[0])
                if po != pn and (pn.startswith(po) or po.startswith(pn)) and abs(lo - ln) <= 5:
                    return o if lo < ln else n     # a scrap on the end of the same line: the line without it
                wo, wn = wordy(o[0]), wordy(n[0])
                if abs(wo - wn) > 0.25:
                    return o if wo > wn else n     # the reading made of words stands over the squashed one
                ho, hn = "sn-h" in o[1], "sn-h" in n[1]
                if ho != hn and abs(lo - ln) <= 15:
                    return n if ho else o          # a heading one moment, plain the others: plain
                return n if (ln, n[0].count("*")) > (lo, o[0].count("*")) else o
            self.lines = stitch(self.lines, pairs, key=lambda p: p[0], same=same_doc_line, merge=merge)
            plains = [plain_line(t) for t, _ in self.lines]
            joined = set()
            for i, p in enumerate(plains):
                # a line that is two other lines run together (one reading
                # took the wrapped pair as one) gives way to the pair
                inside = [j for j, q in enumerate(plains) if j != i and len(q) >= 10 and q in p and len(q) < len(p)]
                if len(inside) >= 2 and sum(len(plains[j]) for j in inside[:3]) >= 0.7 * len(p):
                    joined.add(i)
            kept = []
            for i, (t, h) in enumerate(self.lines):
                if i in joined:
                    continue
                n = plain_line(t)
                if len(n) >= 12 and any(j != i and j not in joined and len(plain_line(u)) > len(n) and n in plain_line(u)
                                        for j, (u, _) in enumerate(self.lines)):
                    continue          # held whole by a longer line
                kept.append((t, h))
            self.lines = kept
        else:
            self.lines = stitch(self.lines, pairs, key=lambda p: p[0], same=same_text)
        if self.kind == "a file tree":
            # a folder with rows under it deeper than itself is open
            fixed = []
            for i, (t, h) in enumerate(self.lines):
                after = [x for x, _ in self.lines[i + 1:i + 3]]
                if "˃" in t and len(after) == 2 and all(tree_depth(x) > tree_depth(t) for x in after):
                    t2 = t.replace("˃", "˅", 1)
                    h = h.replace(esc(t), esc(t2)) if esc(t) in h else esc(t2)
                    t = t2
                fixed.append((t, h))
            self.lines = fixed


    def identity(self):
        """The first stretch of the text, marks stripped: a note is the same
        note when this reads alike, whatever rank the reader gave a line."""
        body = [t.strip("#*> ") for t, _ in self.lines if t.strip() and not t.startswith("---")]
        return norm(" ".join(body))[:240]

    def title(self):
        """The note's title: its first line that is not a property, a bar
        or a scrap."""
        for t, _ in self.lines:
            t = t.strip().strip("#*> ").strip()
            if not t or t.startswith("---") or old.is_bar(t):
                continue
            if len(norm(t)) < 4:
                continue
            return t
        return ""


# ------------------------------------------------------------- pane -> content

def tree_pairs(pane):
    """The tree as the reader drew it, guides and chevrons included; a row
    on a coloured band keeps its colour."""
    d = pane.get("data") or {}
    rows = d.get("rows") or []
    banded = {r["name"]: r["band"] for r in rows if r.get("band") and r.get("name")}
    out, fine = [], []
    for ln in old.content_lines(pane):
        text = ln.rstrip()
        if not text.strip():
            continue
        h = esc(text)
        hue = next((hue for name, hue in banded.items() if text.strip().endswith(name)), None)
        if hue:
            h = f'<span class="sn-{hue}" style="font-weight:600">{h}</span>'
        out.append((text, h))
    for r in rows:
        if r.get("name_status") == "uncertain" and r.get("name_second"):
            fine.append(f"{r.get('name')} / {r['name_second']}")
    return out, fine


def doc_pairs(pane):
    out, fine, props, in_props = [], [], [], False
    doubt = set()
    for raw in pane.get("lines") or []:
        s = raw.strip()
        if s.startswith(("[also on this pane", "unsettled:", "[dark look", "[light look")):
            if s.startswith("unsettled:"):
                fine.append(s[len("unsettled:"):].strip())
            continue
        if s == "---":
            if in_props:
                out.append(("---props", '<div class="sn-props">' + "<br>".join(esc(p) for p in props) + "</div>"))
                props = []
            in_props = not in_props
            continue
        if in_props:
            k, _, v = s.partition(":")
            if re.fullmatch(r"[a-z_][a-z0-9_-]*", k.strip()) and len(v.strip()) >= 2:
                props.append(s)
            continue
        # a heading whose text begins lowercase is a cut line ranked by its
        # letter height, not a heading; an unpaired bold mark is a scrap
        body, _, tail = raw.partition(" <- ")
        m = re.match(r"^(\s*)(#{1,6}) ([a-z].*)$", body)
        if m:
            raw = m.group(1) + m.group(3) + ((" <- " + tail) if tail else "")
        m = re.match(r"^(\s*)(#{1,6}) (.{60,})$", body)
        if m and m.group(3).rstrip().endswith((".", ":", ",")):
            raw = m.group(1) + m.group(3) + ((" <- " + tail) if tail else "")
        if body.count("**") % 2 == 1:
            raw = raw.replace("**", "", 1) if raw.count("**") % 2 == 1 else raw
        h = old.doc_line(raw, fine)
        if h is None or not s:
            continue
        text = re.split(r"\s+<- ", raw.rstrip())[0].strip()
        out.append((text, h))
        if "one engine" in tail:
            doubt.add(text)
    doc_pairs.doubt = doubt
    return out, fine


# ------------------------------------------------------------- states

GENERIC = {"macintoshhd", "users", "documents", "jaredr", "jaredrhodenizer", "jaredrhodenize"}
FINDER_WORDS = {"Name", "Date Modified", "Size", "Kind", "Date Created", "Date Added", "Date Modified Size", "Size Kind"}

NAMED = {"Finder": "The Finder window", "Obsidian": "The Obsidian window", "The browser": "The browser window",
         "The terminal": "The terminal window", "The chat": "The chat window"}


def window_name(group_name):
    return NAMED.get(group_name, group_name)


def is_real_window(name):
    return name in NAMED.values()


def folder_marks(table):
    """The crumbs that name the folder, the generic ones left out."""
    return {norm(c) for c in table.path if norm(c) not in GENERIC and len(norm(c)) >= 3}


class State:
    """One window showing one thing, across the moments it was on screen.

    Its content is a list of parts in left-to-right order, each a table,
    a tree, a note, a terminal or a strip of words, keyed by kind and the
    eighth of the screen it starts in; a later moment's pane joins the
    part in its place, so a scrolled note grows and a list gains rows."""
    def __init__(self, group, ts):
        self.name = window_name(group["name"])
        self.title = group.get("title")
        self.rect = group["rect"]
        self.where = group.get("where")
        self.times = [ts]
        self.parts = []         # {"kind", "slot", "model"}
        self.fine = []
        self.furniture = []      # words read above a tree: tab strips, menus
        self.topwords = []       # (text, x0, y0, x1, y1, ok) read along the top of the frame
        self.covered = False     # the camera picture covered part of the window
        self.said = []
        self.theme = None

    # --------------------------------------------------------- content in

    def part_for(self, kind, slot):
        fam = {"a list of columns": "table", "a file tree": "tree", "an open document": "doc",
               "a terminal": "term", "a chat log": "term"}.get(kind, "words")
        for part in self.parts:
            if part["fam"] == fam and abs(part["slot"] - slot) <= 1:
                return part
        model = Table() if fam == "table" else (Lines(kind) if fam in ("tree", "doc", "term") else [])
        part = {"fam": fam, "slot": slot, "model": model, "x0": None, "x1": None}
        self.parts.append(part)
        self.parts.sort(key=lambda q: q["slot"])
        return part

    def absorb(self, group, m):
        W = (m.get("size") or [1920])[0]
        rect = group["rect"]
        for p in sorted(group["panes"], key=lambda p: (p["box"][0], p["box"][1])):
            if p.get("since") or p.get("same_as"):
                continue
            k = p["kind"]
            slot = int(8 * p["box"][0] / max(1, W))
            if k == "an open document":
                # the tree, scrolled so far that the reader saw a plain list
                # of names where the tree stood: those names are its rows
                tree_part = next((q for q in self.parts if q["fam"] == "tree" and q["x0"] is not None
                                  and min(q["x1"], p["box"][2]) - max(q["x0"], p["box"][0]) >= 0.5 * (p["box"][2] - p["box"][0])), None)
                if tree_part:
                    names = [t for t, _ in doc_pairs(p)[0]]
                    names = [re.sub(r"(\.{2,}|…)$", "...", n.strip().strip("#*> ").strip()) for n in names if not n.startswith("---")]
                    namelike = [n for n in names if n.rstrip(".").count(" ") <= 2 and "..." not in n.rstrip(".")
                                and re.search(r"[a-z]{4}", n) and not old.CLOCK.match(n)
                                and all(w[:1].isupper() or w[:1].isdigit() for w in n.split()[1:])]
                    namelike = [n for n in namelike if not any(same_text(n, f) for f in self.furniture)]
                    if names and len(namelike) >= 0.6 * len(names):
                        tree = tree_part["model"]
                        twin = next((t for t, _ in tree.lines if any(same_text(t.strip("│ ˃˅"), n) for n in namelike)), None)
                        indent = twin[:len(twin) - len(twin.lstrip("│ "))] if twin else ""
                        tree.add([(indent + n, esc(indent + n)) for n in namelike])
                        tree_part["x0"] = min(tree_part["x0"], p["box"][0])
                        tree_part["x1"] = max(tree_part["x1"], p["box"][2])
                        continue
            part = self.part_for(k, slot)
            part["x0"] = p["box"][0] if part["x0"] is None else min(part["x0"], p["box"][0])
            part["x1"] = p["box"][2] if part["x1"] is None else max(part["x1"], p["box"][2])
            if k == "a list of columns":
                tables = draw2.build_tables(p)
                built = max(tables, key=lambda t: len(t[3])) if tables else None
                if built and len(built[3]) < 6:
                    # the reader's block was a sliver; the words' positions
                    # may hold the whole list
                    loose = draw2.table_from_loose(p)
                    if loose and len(loose[3]) > len(built[3]):
                        built = loose
                if built:
                    part["model"].add(built)
                    if len(tables) > 1 and built[6]:
                        # this list's own span, not the pane's two windows
                        part["x0"], part["x1"] = built[6]
            elif k == "a file tree":
                pairs, fine = tree_pairs(p)
                part["model"].add(pairs)
                self.fine.extend(fine)
                for r in (p.get("data") or {}).get("remainder") or []:
                    if r.get("where") == "above" and r.get("text"):
                        self.furniture.append(r["text"])
            elif k == "an open document":
                pairs, fine = doc_pairs(p)
                part["model"].doubt |= doc_pairs.doubt
                part["model"].add(pairs)
                self.fine.extend(fine)
            elif k in ("a terminal", "a chat log"):
                pairs = [(ln, esc(ln)) for ln in old.content_lines(p) if ln.strip()]
                part["model"].add(pairs)
            else:
                built = draw2.table_from_loose(p)
                have = next((q for q in self.parts if q["fam"] == "table"), None)
                if built and have:
                    # the list read loose again: the same folder's rows and
                    # sidebar join the table already here; another folder
                    # behind stays words
                    names_new = {norm(c[0]) for c, _, _ in built[3] if c and c[0]}
                    names_old = set(have["model"].names())
                    shared = len(names_new & names_old) / max(1, min(len(names_new), len(names_old)))
                    if shared >= 0.5 or not names_old:
                        self.parts.remove(part)
                        have["model"].add(built)
                        if built[6]:
                            have["x0"] = min(have["x0"], built[6][0]) if have["x0"] is not None else built[6][0]
                            have["x1"] = max(have["x1"], built[6][1]) if have["x1"] is not None else built[6][1]
                        continue
                    built = None
                if built:
                    # a list the reader left loose: its table, rebuilt
                    self.parts.remove(part)
                    tpart = self.part_for("a list of columns", slot)
                    tpart["x0"], tpart["x1"] = (built[6] if built[6] else (p["box"][0], p["box"][2]))
                    tpart["model"].add(built)
                    continue
                lines, fine = draw2.block_loose(p, rect)
                self.fine.extend(fine)
                words = part["model"]
                for ln in lines:
                    label, _, rest = ln.partition(":** ")
                    for w in (rest or ln).replace(" &nbsp; ", " · ").split(" · "):
                        w = w.strip()
                        if w and not any(same_text(w, x) for x in words):
                            words.append(w)
        th = old.theme_of(group["panes"])
        self.theme = self.theme or th
        H = (m.get("size") or [0, 2160])[1]
        for p in group["panes"]:
            for it in draw2.items_of(p):
                if it["box"][3] <= 0.09 * H and it["role"] in ("loose", "left"):
                    if not any(same_text(it["text"], t[0]) and abs(t[2] - it["box"][1]) < 0.01 * H for t in self.topwords):
                        self.topwords.append((it["text"], it["box"][0], it["box"][1], it["box"][2], it["box"][3], it["ok"]))
            d = p.get("data") or {}
            if d.get("video_words") or any("runs past the pane" in ln for ln in (p.get("lines") or [])):
                self.covered = True
        t = self.main_table()
        if t and not is_real_window(self.name) and sum(1 for h in t.header if h in FINDER_WORDS) >= 2:
            self.name = "The Finder window"
        if m["ts"] not in self.times:
            self.times.append(m["ts"])
        table = self.main_table()
        if table and (not self.title or not getattr(self, "title_sure", False) or getattr(self, "title_from_path", False)):
            # the folder's name. Finder centres it in the title bar, so the
            # confirmed top word nearest the list's centre is the title;
            # failing that, the top word that is also a crumb of the path;
            # failing that, the path's last crumb
            tpart = next((q for q in self.parts if q["fam"] == "table" and q["model"] is table), None)
            tops = [(t, cx) for t, cx, ok, above in table.top_items
                    if ok and above <= 4 and not re.fullmatch(r"[0O]+", t) and len(t) >= 3 and t not in FINDER_WORDS]
            hit = None
            crumbs = [c for path in reversed(table.paths) for c in reversed(path)]
            for c in crumbs:
                hit = next((t for t, _ in tops if same_text(t, c) or norm(t).startswith(norm(c))), None)
                if hit:
                    break
            if hit:
                self.title, self.title_sure, self.title_from_path = hit, True, False
                return
            if self.title:
                return                # keep what an earlier moment gave
            self.title_sure = False
            if tpart and tpart["x0"] is not None and tops:
                mid = (tpart["x0"] + tpart["x1"]) / 2
                width = max(1, tpart["x1"] - tpart["x0"])
                near = min(tops, key=lambda tc: abs(tc[1] - mid))
                if abs(near[1] - mid) <= 0.25 * width:
                    hit = near[0]
            end = table.path[-1] if table.path else ""
            if hit:
                self.title = hit
            elif end and norm(end) not in GENERIC:
                self.title = end
                self.title_sure = True
                self.title_from_path = True

    # --------------------------------------------------------- identity

    def main_table(self):
        tables = [q["model"] for q in self.parts if q["fam"] == "table"]
        return max(tables, key=lambda t: len(t.rows)) if tables else None

    def main_doc(self):
        docs = [q["model"] for q in self.parts if q["fam"] == "doc"]
        return max(docs, key=lambda d: len(d.lines)) if docs else None

    def tree(self):
        trees = [q["model"] for q in self.parts if q["fam"] == "tree"]
        return max(trees, key=lambda d: len(d.lines)) if trees else None

    def words(self):
        return [w for q in self.parts if q["fam"] == "words" for w in q["model"]]

    def fragment(self):
        """An untitled sliver of a list: under three rows and nothing else."""
        t = self.main_table()
        others = [q for q in self.parts if q["fam"] in ("tree", "doc", "term")]
        if not self.title and not t and not others:
            return True           # words only: a window behind, showing through
        return bool(t) and not getattr(self, "title_sure", False) and len(t.rows) < 3 and not others

    def has_content(self):
        return any((q["model"].rows if q["fam"] == "table" else q["model"].lines if q["fam"] in ("tree", "doc", "term") else q["model"]) for q in self.parts)

    def same_thing(self, other):
        """The same window showing the same thing. A list shows the same
        folder when half its row names are shared, or the lists overlap at
        an edge (scrolled), or two long lists with no row in common have
        paths naming the same folder; a note is the same note by its
        title; a tree alone by its first rows; words by their likeness."""
        if self.name != other.name:
            return False
        ta, tb = self.main_table(), other.main_table()
        if ta and tb:
            a, b = set(ta.names()), set(tb.names())
            # a fragment of a window already drawn: the same folder name
            if self.title and other.title and same_text(self.title, other.title) and min(len(a), len(b)) < 3:
                return True
            if not a or not b:
                # a reading with the names out of view: the same list when
                # its other cells repeat rows of the other
                nameless, named = (ta, tb) if not a else (tb, ta)
                rests = [" ".join(r["cells"][1:]).strip() for r in nameless.rows]
                rests = [r for r in rests if r]
                have = [" ".join(r["cells"][1:]).strip() for r in named.rows]
                hits = sum(1 for r in rests if any(same_text(r, h) for h in have))
                return bool(rests) and hits * 2 >= len(rests) and len(rests) >= 2
            if len(a & b) / min(len(a), len(b)) >= 0.5:
                return True
            an, bn = ta.names(), tb.names()
            if any(x == bn[0] for x in an[-3:]) or any(x == an[0] for x in bn[-3:]):
                return True
            if len(an) >= 10 and len(bn) >= 10 and not (a & b):
                fa, fb = folder_marks(ta), folder_marks(tb)
                return bool(fa and fb and fa & fb)
            return False
        if ta or tb:
            return False
        da, db = self.main_doc(), other.main_doc()
        if da and db:
            # notes compared by position: any note in the same place that
            # is the same note (by title, else by its first stretch)
            def same_doc(x_, y_):
                tx, ty = norm(x_.title()), norm(y_.title())
                if tx and ty and len(min(tx, ty, key=len)) >= 6 and (tx.startswith(ty) or ty.startswith(tx)):
                    return True
                x, y = x_.identity(), y_.identity()
                return bool(x and y) and (x == y or difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.75)
            mine = [q for q in self.parts if q["fam"] == "doc"]
            theirs = [q for q in other.parts if q["fam"] == "doc"]
            for q in mine:
                for r in theirs:
                    if abs(q["slot"] - r["slot"]) <= 1 and same_doc(q["model"], r["model"]):
                        return True
            return False
        if da or db:
            return False
        ra, rb = self.tree(), other.tree()
        if ra and rb:
            # the same tree, scrolled: rows in common, or one's end at the
            # other's start
            a = [norm(t) for t, _ in ra.lines if norm(t)]
            b = [norm(t) for t, _ in rb.lines if norm(t)]
            if not a or not b:
                return False
            if len(set(a) & set(b)) / min(len(a), len(b)) >= 0.3:
                return True
            return any(x == b[0] for x in a[-3:]) or any(x == a[0] for x in b[-3:])
        if ra or rb:
            return False
        wa, wb = norm(" ".join(self.words())), norm(" ".join(other.words()))
        return bool(wa and wb) and difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio() >= 0.8

    # --------------------------------------------------------- the drawing

    def heading(self):
        if len(self.times) == 1:
            span = self.times[0]
        elif len(self.times) == 2:
            span = f"{self.times[0]} and {self.times[1]}"
        else:
            span = f"{self.times[0]} to {self.times[-1]}"
        what = f", {self.title}" if self.title else ""
        return f"## {self.name}{what} - as at {span}"

    def window_html(self):
        import furnish
        html = furnish.window(self)
        if html is not None:
            return html
        return self.plain_window_html()

    def plain_window_html(self):
        table = self.main_table()
        side_words, top_words, path, bottom = [], [], [], []
        if table:
            side_words, top_words, path, bottom = list(table.side), list(table.top), list(table.path), list(table.bottom)
        cols = []       # (html, width in frame pixels)
        parts = self.parts
        if self.name == "The Finder window" and table:
            # Finder shows a list; a note or a tree in its frame is the
            # window behind, and a second list is another Finder window
            parts = [q for q in self.parts if q["fam"] == "words" or (q["fam"] == "table" and q["model"] is table)]
        for q in parts:
            fam, model = q["fam"], q["model"]
            width = max(1, (q["x1"] or 0) - (q["x0"] or 0))
            if fam == "table":
                cols.append(('<div class="sn-body">' + model.html() + "</div>", width))
            elif fam == "tree":
                cols.append(('<div class="sn-tree">' + "\n".join(h for _, h in model.lines) + "</div>", width))
            elif fam == "doc":
                cols.append(('<div class="sn-doc">' + doc_html(model) + "</div>", width))
            elif fam == "term":
                cols.append(('<div class="sn-tree">' + "\n".join(h for _, h in model.lines) + "</div>", width))
            else:
                if not model:
                    continue
                # a strip of words is drawn only as the sidebar of a list
                # that has none of its own and stands to its right; other
                # strips (tabs, clocks, the window behind) stay in the record
                table_part = next((t for t in self.parts if t["fam"] == "table"), None)
                if (table_part and not side_words and q["x1"] is not None and table_part["x0"] is not None
                        and q["x1"] <= table_part["x0"] + 0.02 * (table_part["x1"] - table_part["x0"])
                        and len(model) >= 3 and all(len(w) <= 24 for w in model)):
                    side_words = list(model)
                elif len(self.parts) == 1:
                    cols.append(('<div class="sn-body">' + " &nbsp;·&nbsp; ".join(esc(w) for w in model) + "</div>", width))
        if not (cols or side_words):
            return ""
        title_bar = ""
        if self.title:
            title_bar = f'<div class="sn-titlebar"><b>{esc(self.title)}</b></div>'
        if side_words:
            # the list's own sidebar: a fifth of the table's width, at its left
            table_part = next((q for q in self.parts if q["fam"] == "table" and q["model"] is table), None)
            tw = max(1, (table_part["x1"] or 0) - (table_part["x0"] or 0)) if table_part else 1000
            side = ('<div class="sn-side">' + "<br>".join(esc(w) for w in side_words) + "</div>", max(160, int(0.22 * tw)))
            at = cols.index(next(c for c in cols if c[0].startswith('<div class="sn-body">'))) if table_part else 0
            cols.insert(at, side)
        if len(cols) >= 2:
            total = sum(w for _, w in cols) or 1
            fr = " ".join(f"{max(8, round(100 * w / total))}fr" for _, w in cols)
            body = f'<div class="sn-cols" style="grid-template-columns: {fr}">' + "".join(h for h, _ in cols) + "</div>"
        else:
            body = "".join(h for h, _ in cols)
        foot = ""
        if path:
            foot = '<div class="sn-pathbar">' + "›".join(f"<span>{esc(c)}</span>" for c in path) + "</div>"
        elif bottom:
            foot = '<div class="sn-pathbar">' + " &nbsp;·&nbsp; ".join(esc(w) for w in bottom) + "</div>"
        cls = "sn-window sn-dark" if self.theme == "dark" else "sn-window"
        return f'<div class="{cls}">{title_bar}{body}{foot}</div>'

    def said_html(self):
        out = []
        for ts, text in self.said:
            text = text.strip()
            if not text:
                continue
            out.append(f"> [!quote]- Jared, {ts} ({len(text.split())} words)\n> {text}")
        return out

    def fine_html(self):
        seen, kept = set(), []
        for f in self.fine:
            f = re.sub(r"\s+", " ", f).strip()
            if not re.search(r" / | read as |only one engine|underlin|wobbl|off the|not read", f):
                continue          # a bare word says nothing
            if f and f not in seen:
                seen.add(f)
                kept.append(f)
        if not kept:
            return ""
        more = f"; and {len(kept) - MAX_DOUBT} more" if len(kept) > MAX_DOUBT else ""
        return '<span class="sn-fine">fine print: ' + "; ".join(esc(x) for x in kept[:MAX_DOUBT]) + more + "</span>"


def build_states(moments):
    """Walk the moments; each window group joins the open state showing
    the same thing, or opens a new state."""
    states = []
    open_by_slot = {}          # window name + where it stands -> its current state
    for m in moments:
        groups = draw2.window_groups(m)
        W = (m.get("size") or [1920])[0]
        seen = set()
        for g in groups:
            probe = State(g, m["ts"])
            probe.absorb(g, m)
            if not probe.has_content():
                continue
            slot = draw2.group_key(g, W)
            all_repeat = all(p.get("since") or p.get("same_as") for p in g["panes"])
            # the open state in this slot first (a repeat is judged against
            # it), then every earlier state of the same window, latest
            # first: a window can scroll back to what it showed before
            here = open_by_slot.get(slot)
            cands = ([here] if here else []) + [st for st in reversed(states) if st.name == probe.name and st is not here]
            cur = None
            if here and all_repeat:
                cur = here
            else:
                cur = next((c for c in cands if c.same_thing(probe)), None)
            if cur is not None:
                t = probe.main_table()
                sliver = bool(t) and len(t.rows) < 3
                if not all_repeat and not sliver:
                    cur.absorb(g, m)
                elif m["ts"] not in cur.times:
                    cur.times.append(m["ts"])
                st = cur
            else:
                st = probe
                states.append(st)
            open_by_slot[slot] = st
            seen.add(slot)
        said = (m.get("said") or "").strip()
        if said:
            # the words go under the window that was the moment's subject:
            # the biggest state touched this moment
            touched = [open_by_slot[k] for k in seen if k in open_by_slot]
            if touched:
                home = max(touched, key=lambda s: (s.rect[2] - s.rect[0]) * (s.rect[3] - s.rect[1]))
                home.said.append((m["ts"], said))
    harmonise(states)
    return states


def flat(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def rebuild_line(h, t):
    """A plain doc line's HTML rebuilt around mended text, its class,
    indent and cut mark kept; None when the line is not a plain div."""
    m = re.match(r'<div( class="[^"]*")?>((?:&nbsp;)*)', h)
    if not m:
        return None
    body = esc(t.strip())
    body = old.BOLD.sub(r"<b>\1</b>", body)
    body = old.ITALIC.sub(r"<i>\1</i>", body)
    return f"<div{m.group(1) or ''}>{m.group(2) or ''}{body}{'…' if '…</div>' in h else ''}</div>"


def mend_doc(model, st, clean):
    """A note's lines mended from the pool: numbered map entries take their
    real numbers, scraps the camera cut loose drop away, and a line cut at
    the pane's edge sheds the junk the cut left on its end."""
    nums = {}
    for c in clean:
        m = re.match(r"^(\d\d) (\w+)", c)
        if m:
            nums.setdefault(m.group(2).lower(), set()).add(m.group(1))
    fixed = []
    for t, h in model.lines:
        old_t = t
        if not t.startswith("---"):
            plain = plain_line(t)
            if len(plain) <= 4 and len(re.findall(r"[A-Za-z]+", t)) <= 1:
                continue                       # a scrap cut loose from its line
            m = re.match(r"^\s*(\d+) files, (\d+) folders\s*$", t)
            if m:
                st.explorer_count = t.strip()  # the explorer's count, read into the note
                continue
        m = re.match(r"^(\s*[*•\-]\s*)([0-9@OoQ]{2})(?=\s+\S)", t)
        if m and not m.group(2).isdigit():
            t = t[:m.start(2)] + re.sub(r"[@OoQ]", "0", m.group(2)) + t[m.end(2):]
        m = re.match(r"^(\s*[*•\-]\s*)(\d\d)\s+(\w+)", t)
        if m:
            good = nums.get(m.group(3).lower(), set())
            if good and m.group(2) not in good:
                pick = [g for g in good if sum(1 for x, y in zip(g, m.group(2)) if x != y) <= 1]
                if len(pick) == 1:
                    t = t[:m.start(2)] + pick[0] + t[m.end(2):]
        if "…</div>" in h:
            while True:
                t2 = re.sub(r"\s*[:;'\"‘’|_.\]})]+$", "", t)
                if re.search(r"[A-Za-z]{2}\s+[A-Za-z]$", t2):
                    t2 = re.sub(r"\s+[A-Za-z]$", "", t2)
                if t2 == t:
                    break
                t = t2
        if t != old_t:
            h2 = rebuild_line(h, t)
            if h2 is None:
                t = old_t
            else:
                h = h2
        fixed.append((t, h))
    model.lines = fixed


NUM_RX = re.compile(r"^([0OoQ][0-9OoQ])(?=[ A-Za-z])")


def mend_numbered(name, siblings):
    """In a numbered family ("00 Inbox", "01 Daily Notes"...) a leading
    o/O/Q is a misread 0, and the space after the number comes back."""
    if sum(1 for s in siblings if re.match(r"^\d\d[ A-Z]", s)) < 2:
        return name
    m = NUM_RX.match(name)
    if m and not m.group(1).isdigit():
        name = m.group(1).replace("o", "0").replace("O", "0").replace("Q", "0") + name[2:]
    if re.match(r"^\d\d[A-Za-z]", name):
        name = name[:2] + " " + name[2:]
    return name


def harmonise(states):
    """One name, read clean somewhere, stands everywhere it was read badly:
    a tree row or a doubtful list cell that reads alike a confirmed name
    from a list takes that name. The golden drawing did this by hand
    ("03 Company B (Landscape Company)" from the tree where it read clean)."""
    # numbered names mended first, so the pool itself is clean; the fine
    # print waits for the settled name at the end of the pass
    for st in states:
        for q in st.parts:
            if q["fam"] == "table":
                names = [r["cells"][0] for r in q["model"].rows if r["cells"] and r["cells"][0]]
                for r in q["model"].rows:
                    if r["cells"] and r["cells"][0]:
                        b = mend_numbered(r["cells"][0], names)
                        if b != r["cells"][0]:
                            r["_orig"] = r["cells"][0]
                            r["cells"][0] = b
            elif q["fam"] == "tree":
                names = [t.lstrip("│ ˃˅") for t, _ in q["model"].lines]
                fixed = []
                for t, h in q["model"].lines:
                    lead = t[:len(t) - len(t.lstrip("│ ˃˅"))]
                    name = t[len(lead):]
                    b = mend_numbered(name, names)
                    if b != name:
                        h = h.replace(esc(name), esc(b)) if esc(name) in h else esc(lead + b)
                        t = lead + b
                    fixed.append((t, h))
                q["model"].lines = fixed
    clean = []
    for st in states:
        if st.title and len(st.title) >= 3 and st.title not in clean:
            clean.append(st.title)
        for q in st.parts:
            if q["fam"] == "tree":
                for t, _ in q["model"].lines:
                    n = t.lstrip("│ ˃˅")
                    if len(n) >= 6 and "..." not in n and "…" not in n and n not in clean and " " not in n[:1]:
                        clean.append(n)
            if q["fam"] != "table":
                continue
            for c in q["model"].path:
                if len(c) >= 5 and c not in clean and not c.endswith("…"):
                    clean.append(c)
            for r in q["model"].rows:
                if r["cells"] and r["cells"][0] and not (r["italic"] and r["italic"][0]):
                    n = r["cells"][0]
                    if len(n) >= 3 and "..." not in n and n not in clean:
                        clean.append(n)

    # one canonical spelling per name: among every reading that flattens
    # alike, the one with the most of its letters intact (capitals, dots,
    # spaces survive OCR worst, so the fullest form is the truest)
    canon = {}
    for c in clean + [w for w in draw2.SIDEBAR_WORDS if len(w) >= 5]:
        f = flat(c)
        cur = canon.get(f)
        rank = (sum(1 for ch in c if ch.isupper()), len(c))
        if cur is None or rank > (sum(1 for ch in cur if ch.isupper()), len(cur)):
            canon[f] = c

    def exact_fix(name):
        f = flat(name)
        c = canon.get(f)
        if c and c != name:
            return c
        if c is None and f.endswith("md") and len(f) >= 10:
            base = canon.get(f[:-2])
            if base and len(flat(base)) >= 8 and not base.lower().endswith(".md"):
                return base + ".md"
        return None

    def better(name, fuzzy=False):
        f = flat(name)
        if len(f) < 4:
            return None
        b = exact_fix(name)
        if b:
            return b
        if name in clean:
            return None
        for c in clean:
            cf = flat(c)
            if fuzzy and len(cf) >= 6 and difflib.SequenceMatcher(None, cf, f, autojunk=False).ratio() >= 0.85:
                return canon.get(cf, c)
            if "..." in name:
                a, _, b2 = name.partition("...")
                af, bf = flat(a), flat(b2)
                if af and bf and cf.startswith(af) and cf.endswith(bf) and len(af) + len(bf) >= 8:
                    return canon.get(cf, c)
        return None

    def rescue(name):
        """A name every engine mangled: the one pool name it still half
        resembles, when no other comes close. Only a name that no longer
        looks like a file name at all is up for rescue."""
        if "_" in name or "..." in name or " " not in name:
            return None
        f = re.sub(r"(md|m d)$", "", flat(name))
        if len(f) < 8:
            return None
        scored = sorted(((difflib.SequenceMatcher(None, re.sub(r"md$", "", flat(c)), f, autojunk=False).ratio(), c)
                         for c in clean if len(flat(c)) >= 8), reverse=True)
        if scored and scored[0][0] >= 0.5 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.08):
            c = scored[0][1]
            if re.search(r"(\.md|\bmd)$", name.strip()) and not c.lower().endswith(".md"):
                c += ".md"
            return c
        return None

    for st in states:
        for q in st.parts:
            if q["fam"] == "tree":
                fixed = []
                for t, h in q["model"].lines:
                    lead = t[:len(t) - len(t.lstrip("│ ˃˅"))]
                    name = t[len(lead):]
                    b = better(name, fuzzy=True)
                    if b:
                        b = re.sub(r"\.md$", "", b)      # the tree shows names without .md
                    if b and b != name:
                        st.fine.append(f"{name} read as {b} in the list")
                        t2 = lead + b
                        fixed.append((t2, h.replace(esc(name), esc(b)) if esc(name) in h else esc(t2)))
                    else:
                        fixed.append((t, h))
                q["model"].lines = fixed
            elif q["fam"] == "table":
                table = q["model"]
                fixed_side = []
                for w in table.side:
                    full = next((c for c in clean if c != w and len(w) >= 5 and c.endswith(w)), None)
                    fixed_side.append(full or w)
                table.side = fixed_side
                for r in table.rows:
                    if not r["cells"] or not r["cells"][0]:
                        continue
                    n = r["cells"][0]
                    orig = r.pop("_orig", n)
                    doubtful = (r["italic"] and r["italic"][0]) or "..." in n
                    b = better(n, fuzzy=doubtful)
                    if not b and doubtful and not any(c for c in r["cells"][1:] if tidy_date(c) or tidy_size(c)):
                        b = rescue(n)
                    if b and b != n:
                        r["cells"][0] = b
                        r["italic"][0] = False
                        n = b
                    if n != orig and flat(n) != flat(orig):
                        st.fine.append(f"{orig} read as {n} elsewhere")
                # a list of hidden files: when two names in three start with
                # a dot, a name without one lost it to the reader
                dotted = sum(1 for r in table.rows if r["cells"] and r["cells"][0].startswith("."))
                named = sum(1 for r in table.rows if r["cells"] and r["cells"][0])
                lost_dots = []
                if named and dotted * 3 >= named * 2:
                    for r in table.rows:
                        if r["cells"] and r["cells"][0] and not r["cells"][0].startswith("."):
                            lost_dots.append(r["cells"][0])
                            r["cells"][0] = "." + r["cells"][0]
                if lost_dots:
                    st.fine.append("read with the leading dot lost: " + ", ".join(lost_dots))
                # the path bar's crumbs completed from the same pool (Finder
                # cuts long crumbs short; the folder's real name stands)
                pool = clean + [w for w in draw2.SIDEBAR_WORDS if len(w) >= 5]
                for path in [table.path] + table.paths:
                    for i, c in enumerate(path):
                        f = flat(c)
                        b = next((p for p in pool if flat(p) == f and p != c), None)
                        if not b and len(f) >= 4:
                            starts = [p for p in pool if flat(p).startswith(f) and flat(p) != f]
                            if len({flat(p) for p in starts}) == 1:
                                b = starts[0]
                        if b:
                            path[i] = b
                # a date cell no engine read whole, whose digits are a clean
                # date's digits, is that date; a kind cell read twice over
                # keeps one telling of itself
                di = next((i for i, h in enumerate(table.header) if h == "Date Modified"), None)
                ki = next((i for i, h in enumerate(table.header) if h == "Kind"), None)
                if di is not None:
                    pool_dates = {}
                    for r in table.rows:
                        if di < len(r["cells"]) and r["cells"][di] and not (r["italic"][di] if di < len(r["italic"]) else False):
                            pool_dates.setdefault(re.sub(r"\D", "", r["cells"][di]), r["cells"][di])
                    for r in table.rows:
                        if di < len(r["cells"]) and r["cells"][di] and tidy_date(r["cells"][di]) is None and DATE_RX.match(r["cells"][di]) is None:
                            hit = pool_dates.get(re.sub(r"\D", "", r["cells"][di]))
                            if hit and hit != r["cells"][di]:
                                st.fine.append(f"{r['cells'][di]} read as {hit} elsewhere")
                                r["cells"][di] = hit
                                if di < len(r["italic"]):
                                    r["italic"][di] = False
                if ki is not None:
                    kinds = {}
                    for r in table.rows:
                        if ki < len(r["cells"]) and r["cells"][ki]:
                            kinds[r["cells"][ki]] = kinds.get(r["cells"][ki], 0) + 1
                    dominant = max(kinds, key=kinds.get) if kinds else ""
                    kindish = re.compile(r"(Folder|Document|file|File|JSON|Application|Image|Alias)")
                    for r in table.rows:
                        if ki >= len(r["cells"]) or not r["cells"][ki] or kindish.search(r["cells"][ki]):
                            continue
                        c = r["cells"][ki]
                        half = c[:len(c) // 2].strip()
                        rest2 = c[len(c) // 2:].strip()
                        if half and difflib.SequenceMatcher(None, flat(half), flat(rest2), autojunk=False).ratio() >= 0.6:
                            c = half              # the two engines' readings run together
                        if dominant and kinds.get(dominant, 0) >= 3 and \
                                difflib.SequenceMatcher(None, flat(c), flat(dominant), autojunk=False).ratio() >= 0.5:
                            st.fine.append(f"{r['cells'][ki]} read as {dominant} elsewhere")
                            r["cells"][ki] = dominant
                            if ki < len(r["italic"]):
                                r["italic"][ki] = False
            elif q["fam"] == "doc":
                mend_doc(q["model"], st, clean)


def desktop(moments):
    """The menu bar's words, read along the top strip of the frame (each
    program's bar with the moments it stood), and the clock from the first
    reading to the last."""
    bars, clocks = [], []          # bars: [words, first ts, last ts]
    day = ""
    for m in moments:
        H = (m.get("size") or [0, 0])[1]
        words = []
        for p in m.get("panes") or []:
            c = old.clock_in(p)
            if c and (not clocks or clocks[-1][1] != c):
                clocks.append((m["ts"], c))
                for r in (p.get("data") or {}).get("readings") or []:
                    dm = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s?([A-Z][a-z]{2})\s?(\d{1,2})\s*\d{1,2}:\d{2}", (r.get("text") or "").strip())
                    if dm and not day:
                        day = f"{dm.group(1)} {dm.group(2)} {dm.group(3)}"
            if p["box"][1] > 0.02 * H:
                continue
            strip = [it for it in draw2.items_of(p) if it["ok"] and it["box"][1] <= 0.015 * H and it["box"][3] <= 0.035 * H]
            words.extend(strip)
        menubar = []
        if words:
            # the bar is the topmost row of words alone; a tab strip below it is a window's
            top_it = min(words, key=lambda it: it["box"][1])
            cy0, h0 = (top_it["box"][1] + top_it["box"][3]) / 2, max(1, top_it["box"][3] - top_it["box"][1])
            words = [it for it in words if abs((it["box"][1] + it["box"][3]) / 2 - cy0) <= 0.6 * h0]
        for it in sorted(words, key=lambda it: it["box"][0]):
            w = it["text"]
            if not old.CLOCK.match(w) and not any(same_text(w, x) for x in menubar) and len(w) <= 24 and " " not in w.strip():
                menubar.append(w)
        if len(menubar) < 3:
            continue
        # the same bar as before when the first word and most words agree
        if bars and bars[-1][0][0] == menubar[0] and len(set(bars[-1][0]) & set(menubar)) >= 0.6 * min(len(menubar), len(bars[-1][0])):
            for w in menubar:
                if w not in bars[-1][0]:
                    bars[-1][0].append(w)
            bars[-1][2] = m["ts"]
        else:
            bars.append([menubar, m["ts"], m["ts"]])
    if not (bars or clocks):
        return []
    right = ""
    if clocks:
        right = (day + " &nbsp; " if day else "") + clocks[0][1] + (f" → {clocks[-1][1]}" if clocks[-1][1] != clocks[0][1] else "")
    out = ["## The desktop", ""]
    for k, (words, t0, t1) in enumerate(bars):
        when = "" if len(bars) == 1 else (t0 if t0 == t1 else f"{t0} to {t1}")
        clock = right if k == 0 else ""
        label = " &nbsp;·&nbsp; ".join(x for x in (esc(when), clock) if x)
        out.append('<div class="sn-menubar"><span>' + " &nbsp; ".join(esc(w) for w in words[:12])
                   + f"</span><span>{label}</span></div>")
    out.append("")
    return out


def state_label(st):
    return st.title or ("as drawn there")


def span_of(st):
    if len(st.times) == 1:
        return st.times[0]
    if len(st.times) == 2:
        return f"{st.times[0]} and {st.times[1]}"
    return f"{st.times[0]} to {st.times[-1]}"


def note(records_path, diary_text=None):
    header, moments, footer = old.load(records_path)
    title = header.get("title") or os.path.basename(os.path.dirname(records_path))
    diary_text = diary_text if diary_text is not None else old.diary(records_path)
    secs = (moments[-1]["secs"] - moments[0]["secs"]) if len(moments) > 1 else 0
    states = [st for st in build_states(moments) if st.window_html() and not st.fragment()]
    real = [st for st in states if is_real_window(st.name)]
    shown = real if real else states          # a video with no named window shows its screens
    windows = []                               # names in order of first appearance
    for st in shown:
        if st.name not in windows:
            windows.append(st.name)
    clocks = [c for m in moments for p in m.get("panes") or [] for c in [old.clock_in(p)] if c]
    parts = [f"# {title}", ""]
    head = f"A screen recording, {old.minutes(secs)} read, {len(moments)} screen moments."
    if windows:
        counts = []
        for w in windows:
            n = sum(1 for st in shown if st.name == w)
            counts.append(f"{w[0].lower() + w[1:]}" + (f" ({n} states)" if n > 1 else ""))
        head += " On screen: " + "; ".join(counts) + "."
    if clocks:
        head += f" The desktop clock read {clocks[0]}" + (f" at the start and {clocks[-1]} at the end." if clocks[-1] != clocks[0] else ".")
    head += " A word in italics was read by one engine only."
    parts += [head, "", "**The order of events**", ""]
    for st in shown:
        parts.append(f"- {span_of(st)} - {st.name[0].lower() + st.name[1:]}" + (f": {st.title}" if st.title else ""))
    parts += ["", "---", ""]
    for w in windows:
        sts = [st for st in shown if st.name == w]
        latest = max(sts, key=lambda st: st.times[-1])     # the last one on screen
        earlier = [st for st in sts if st is not latest]
        parts.append(f"## {w} - as at {span_of(latest)}" + (f", {latest.title}" if latest.title else ""))
        parts.append("")
        parts.append(latest.window_html())
        parts.append("")
        for ln in latest.said_html():
            parts.append(ln)
            parts.append("")
        if latest.fine_html():
            parts.append(latest.fine_html())
            parts.append("")
        if earlier:
            parts.append("Earlier states of this same window: " + " · ".join(
                f"{e.times[0]} {state_label(e)}" for e in earlier) + " (each drawn the same way below)")
            parts.append("")
            for e in earlier:
                parts.append(f"### as at {span_of(e)}" + (f", {e.title}" if e.title else ""))
                parts.append("")
                parts.append(e.window_html())
                parts.append("")
                for ln in e.said_html():
                    parts.append(ln)
                    parts.append("")
                if e.fine_html():
                    parts.append(e.fine_html())
                    parts.append("")
        parts.append("---")
        parts.append("")
    parts += desktop(moments)
    parts += ["", f"> [!note]- The moment-by-moment record, {len(moments)} moments (appendix)", "> ````text"]
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
