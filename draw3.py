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
import collections
import difflib
import html
import os
import re
import sys

import draw as old          # HTML line helpers that do not change
import draw2                 # the geometry: items, tables rebuilt, window groups
import shapes                # where each window sat, measured off the frame

LONG_SAID = 700
MAX_DOUBT = 12
STITCH_MIN = 0.8            # a row or line is "the same" at this ratio


def esc(s):
    return html.escape(str(s), quote=False)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


MAX_NAMES = 6


def junky(s):
    """A reading with no word in it: letters the engines guessed at."""
    toks = re.findall(r"[A-Za-z][A-Za-z'\u2019_.]*", s)
    if not toks:
        return True
    good = sum(1 for t in toks if re.search(r"[aeiouyAEIOUY]", t) and len(t) >= 3)
    return good * 2 < len(toks) or len(re.sub(r"[^A-Za-z0-9]", "", s)) < 4


def flat(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


FOLD = str.maketrans({"0": "o", "1": "l", "i": "l"})


def fold(s):
    return s.translate(FOLD)


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
SIZE_RX = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(bytes?|[KMGT]B)(?:N(?=\s|$))?\s*(.*)$", re.I)


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
        self.spoiled = 0        # lines dropped: two columns misread at once
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
        rows_below = draw2.reading_order(list(bottom), lambda it: it["box"])
        known = {norm(r["cells"][0]) for r in self.rows if r["cells"] and r["cells"][0]}
        known |= {norm(t) for t, _, _, _ in self.top_items if t}
        best = []
        for row in rows_below:
            # the path is the leading run of crumbs on a row; words after
            # it are the window behind showing through. A crumb that is the
            # list's own folder or a row's name continues the run whatever
            # its shape (the path bar names what the window shows).
            run, sure = [], 0
            for it in row:
                c = it["text"].rstrip(">").strip()
                if not (draw2.crumb_like(it["text"]) or norm(c) in known):
                    break
                if run and norm(c) == norm(run[0]):
                    break             # back at the root: a second bar
                run.append(c)
                if (it["ok"] or it["text"].rstrip().endswith(">")
                        or norm(c) in known or norm(c) + "md" in known):
                    sure += 1
            if sure * 2 < len(run):
                run = []              # a row of guesses is not a path bar
            if len(run) >= 2 and len(run) > len(best):
                best = run
            for it in row[len(run):]:
                if it["ok"] and it["text"] not in self.bottom:
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
        for i, h in enumerate(hdr):
            if any(w in h for w in ("Name", "Date Modified", "Size", "Kind")):
                hdr[i] = re.sub(r"[*_]", "", h).strip()     # marks are never the header's own
        for i, h in enumerate(hdr):
            if "Date Modified" in h and h != "Date Modified":
                hdr[i] = "Date Modified"     # what followed belongs to the next column
        def col(want):
            exact = next((i for i, h in enumerate(hdr) if h == want), None)
            return exact if exact is not None else next(
                (i for i, h in enumerate(hdr) if want in h), None)
        di, si, ki = col("Date Modified"), col("Size"), col("Kind")
        if si == di:
            si = next((i for i, h in enumerate(hdr) if h == "Size" and i != di), si)
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
        if ki is not None:
            usual = collections.Counter(r["cells"][ki] for r in self.rows
                                        if ki < len(r["cells"]) and r["cells"][ki])
            usual = {k for k, n in usual.items() if n >= 2}
            for r in self.rows:
                cs = r["cells"]
                if ki < len(cs) and cs[ki] and cs[ki] not in usual:
                    bare = cs[ki][1:].lstrip()      # one stray letter off a misread
                    hit = next((u for u in usual if same_text(bare, u)), None)
                    if hit:
                        cs[ki] = hit
        self.drop_spoiled(di, ki)

    def drop_spoiled(self, di, ki):
        """A line the reader got wrong in two columns at once is a spoiled
        reading, not a file: where nearly every line's date reads as a date
        and its kind is one the list uses, a line that fails both is out."""
        if di is None or ki is None or len(self.rows) < 5:
            return
        dated = [r for r in self.rows if di < len(r["cells"]) and r["cells"][di]]
        if len(dated) < 5:
            return
        good = [r for r in dated if tidy_date(r["cells"][di])]
        if len(good) < 0.8 * len(dated):
            return
        kinds = collections.Counter(norm(r["cells"][ki]) for r in self.rows
                                    if ki < len(r["cells"]) and r["cells"][ki])
        usual = {k for k, n in kinds.items() if n >= 2}
        out = []
        for r in self.rows:
            cs = r["cells"]
            bad_date = di < len(cs) and cs[di] and not tidy_date(cs[di])
            kind = norm(cs[ki]) if ki < len(cs) else ""
            bad_kind = bool(kind) and kind not in usual and not any(
                same_text(kind, k) for k in usual)
            if bad_date and bad_kind:
                self.spoiled += 1
                continue
            out.append(r)
        self.rows = out

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
                ho, hn = "sn-h" in o[1], "sn-h" in n[1]
                if ho != hn and abs(lo - ln) <= 15:
                    return n if ho else o          # a heading one moment, plain the others: plain
                od, nd = o[0] in self.doubt, n[0] in self.doubt
                if od != nd and abs(lo - ln) <= 8:
                    return n if od else o          # the reading both engines backed
                po, pn = plain_line(o[0]), plain_line(n[0])
                if po != pn and (pn.startswith(po) or po.startswith(pn)) and abs(lo - ln) <= 5:
                    return o if lo < ln else n     # a scrap on the end of the same line: the line without it
                wo, wn = wordy(o[0]), wordy(n[0])
                if abs(wo - wn) > 0.25:
                    return o if wo > wn else n     # the reading made of words stands over the squashed one
                # a longer variant whose extra tail is another line's text
                # swallowed two lines in one reading: the shorter stands
                po2, pn2 = plain_line(o[0]), plain_line(n[0])
                co = os.path.commonprefix([po2, pn2])
                if len(co) >= 20:
                    longer, shorter = (o, n) if len(po2) >= len(pn2) else (n, o)
                    tail = max(po2, pn2, key=len)[len(co):]
                    if len(tail) >= 15 and any(tail in plain_line(u) for u, _ in self.lines
                                               if u not in (o[0], n[0])):
                        return shorter
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
            if len(t) > 60 or t.count(" ") > 7:
                continue          # a paragraph, not a title
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
        self.pieces = []        # (moment, group) it was read from, in order
        self.rects = {}         # ts -> the window's rect at that moment
        self.measured = set()   # the moments the reader measured the window itself
        self._stood = None      # where its words sat last, and the edges then

    # --------------------------------------------------------- content in

    def best_shape(self):
        """The shape to draw this window at on its own: the largest of the
        edges actually measured off the screen, and only where none were
        measured, the box its own words sat in."""
        sure = [self.rects[t] for t in self.rects if t in self.measured]
        if sure:
            return max(sure, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        return self.rect

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
        self._absorb(group, m)
        # where the window stood at this moment, measured from what it drew
        self.rects[m["ts"]] = content_rect(self, group, m)

    def _absorb(self, group, m):
        W = (m.get("size") or [1920])[0]
        rect = group["rect"]
        if not any(mm is m for mm, _ in self.pieces):
            self.pieces.append((m, group))
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
        docs = [d for d in docs if d is not self.tree()]
        if not docs:
            return None
        def prose(d):
            return sum(1 for t, _ in d.lines if t.count(" ") >= 3 and "_" not in t)
        return max(docs, key=lambda d: (prose(d), len(d.lines)))

    @staticmethod
    def _namey(model):
        """How much of a lines model reads as a column of file names rather
        than prose: names carry underscores and few spaces."""
        lines = [t.strip().strip("#*>\u2502 \u02c3\u02c5").strip() for t, _ in model.lines]
        lines = [t for t in lines if t and not t.startswith("---")]
        if not lines:
            return 0.0
        namish = sum(1 for t in lines if "_" in t or t.count(" ") <= 1)
        return namish / len(lines)

    def tree(self):
        trees = [q["model"] for q in self.parts if q["fam"] == "tree"]
        if trees:
            return max(trees, key=lambda d: len(d.lines))
        # the tree read as a plain column of names on a document pane: the
        # leftmost doc whose lines are names is the tree standing there
        docs = [q["model"] for q in sorted(self.parts, key=lambda q: q["slot"])
                if q["fam"] == "doc"]
        for d in docs[:1]:
            if len(docs) > 1 and self._namey(d) >= 0.6:
                return d
        return None

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
            if self.title and other.title and same_text(self.title, other.title) and min(len(a), len(b)) < 3 \
                    and not (getattr(self, "title_from_path", False) or getattr(other, "title_from_path", False)):
                # a title taken off a cut path bar names a folder the path
                # passes through, not the folder on show; it cannot merge
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
        html = furnish.window(self, behind=False)
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
                cols.append(('<div class="sn-tree">' + "".join(f"<div>{h}</div>" for _, h in model.lines) + "</div>", width))
            elif fam == "doc":
                cols.append(('<div class="sn-doc">' + doc_html(model) + "</div>", width))
            elif fam == "term":
                cols.append(('<div class="sn-tree">' + "".join(f"<div>{h}</div>" for _, h in model.lines) + "</div>", width))
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
        """The fine print in plain words: what one name was read as
        instead, what one engine alone saw, and how much ran past the
        pane's edge -- counted, not recited."""
        names, engine, cut, other = [], [], 0, []
        seen = set()
        for f in self.fine:
            f = re.sub(r"\s+", " ", f).strip()
            if not f or f in seen:
                continue
            seen.add(f)
            if "runs past the pane" in f:
                cut += 1
                continue
            m = re.match(r"^(.+?) read as (.+?)(?: (?:elsewhere|in the list))?$", f)
            if m:
                was, now = m.group(1).strip(), m.group(2).strip()
                if junky(was) or junky(now) or flat(was) == flat(now):
                    continue      # the change was not worth a reader's time
                names.append((was, now))
                continue
            if "only one engine" in f or " / " in f:
                engine.append(f)
                continue
            if "cut lines completed" in f or "leading dot" in f or "guessed at" in f or "left out" in f:
                other.append(f)
        bits = []
        if names:
            shown = names[:MAX_NAMES]
            bits.append("read as: " + "; ".join(f"{esc(a)} \u2192 {esc(b)}" for a, b in shown)
                        + (f"; and {len(names) - MAX_NAMES} more" if len(names) > MAX_NAMES else ""))
        if cut:
            bits.append(f"{cut} line{'s' if cut != 1 else ''} ran past the pane's edge and could not be read whole")
        if engine:
            bits.append(f"{len(engine)} reading{'s' if len(engine) != 1 else ''} only one engine backed")
        spoiled = sum(p["model"].spoiled for p in self.parts if isinstance(p["model"], Table))
        if spoiled:
            bits.append(f"{spoiled} line{'s' if spoiled != 1 else ''} left out, misread in two columns at once")
        bits.extend(esc(o) for o in other)
        if not bits:
            return ""
        return '<span class="sn-fine">fine print: ' + "; ".join(bits) + "</span>"


def _alike(a, b):
    fa, fb = fold(flat(a)), fold(flat(b))
    if not fa or not fb:
        return False
    if fa == fb:
        return True
    small, big = sorted((fa, fb), key=len)
    return small in big and len(small) >= 0.85 * len(big)


def drop_guessed(states):
    """A line with no word in it is letters the engines guessed at, not a
    thing the screen said; it leaves the trees and notes, and the fine print
    counts it. A ruled line (---) stays: the screen really draws those."""
    for st in states:
        for q in st.parts:
            if q["fam"] not in ("tree", "doc"):
                continue
            model = q["model"]
            kept, gone = [], 0
            for t, h in model.lines:
                bare = t.strip("\u2502 \u02c3\u02c5\u2022\u00b7*#>").strip()
                if bare.startswith("---") or not bare:
                    kept.append((t, h))
                elif junky(bare) or any(_alike(bare.lstrip("G ").strip(), w[0]) for w in st.topwords if len(w[0]) > 8):
                    gone += 1
                else:
                    kept.append((t, h))
            if gone:
                model.lines = kept
                st.fine.append(f"{gone} line{'s' if gone != 1 else ''} of letters the engines guessed at, left out")


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
                cur.rects.setdefault(m["ts"], content_rect(cur, g, m))
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
    retitle_by_rows(states)
    drop_guessed(states)
    if moments:
        W, H = (moments[0].get("size") or [1920, 1080])[:2]
        for st in states:
            settle_rects(st, W, H)
        settle_across(states, [m["ts"] for m in moments], W, H)
    return states


def retitle_by_rows(states):
    """A list window is named by what it lists. The settled path bars say
    which folder holds which; when a window's rows are the children of a
    known folder, its title is that folder, however the title bar read in
    the blur of a moving frame."""
    parent = {}
    for st in states:
        t = st.main_table()
        if not t:
            continue
        for path in ([t.path] if t.path else []) + [p for p in t.paths if p]:
            for a, b in zip(path, path[1:]):
                if a and b:
                    parent.setdefault(fold(b), (b, a))
    for st in states:
        t = st.main_table()
        if not t:
            continue
        votes = {}
        for name in t.names():
            hit = parent.get(fold(name))
            if hit is None:
                # a name the list drew cut short still names its folder
                hit = next((v for k, v in parent.items() if name_fits(name, v[0])), None)
            if hit:
                votes[hit[1]] = votes.get(hit[1], 0) + 1
        if not votes:
            continue
        best = max(votes, key=lambda v: votes[v])
        if st.title and crumb_same(st.title, best):
            continue
        weak = not getattr(st, "title_sure", False) or getattr(st, "title_from_path", False)
        # even a title read off the bar yields when it names another known
        # folder and none of that folder's known children sit in these rows
        named_elsewhere = st.title and any(crumb_same(st.title, v[1]) for v in parent.values()) \
            and not any(crumb_same(parent[fold(n)][1], st.title) for n in t.names() if fold(n) in parent)
        if not st.title or weak or named_elsewhere:
            st.title = best


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
    for _pass in range(2):
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
            t = re.sub(r"\s+[*•\-]\s*$", "", t)
            t = re.sub(r"\s*[|}{\]‘’]+\s*$", "", t)
            t = re.sub(r"\s\|(?=\s)", "", t)
            # a scrap of stray marks the reader dropped between two words
            t = re.sub(r"(?<=[a-z,;])\s+[|_@{}\[\]]+\s+(?=[a-z(])", " ", t)
            # the arrow the note draws, which the engines read as a chevron
            t = re.sub(r"(?<=[a-z\u2019])\s[>\u203a]\s(?=[a-z])", " \u2192 ", t)
            t = re.sub(r"(?<=[.!?])\s+[a-z]{1,3}(\s+[a-z]{1,3})?\s*$", "", t)
            t = re.sub(r"\s*<\s*[a-z]{0,4}\s*$", "", t)
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
            m = re.search(r"\s(\*)\s+[A-Z0-9@]", t)
            if m and rebuild_line(h, t) is not None:
                # a new bullet read into the line before it: two lines
                t1, t2 = t[:m.start()].rstrip(), t[m.start(1):]
                if len(plain_line(t1)) >= 8 and len(plain_line(t2)) >= 12:
                    fixed.append((t1, rebuild_line(h, t1)))
                    ind = "&nbsp;" * 2
                    fixed.append((t2, f"<div>{ind}{esc(t2)}</div>"))
                    continue
            fixed.append((t, h))
        model.lines = fixed
    fixed = model.lines
    # the same line kept twice under two misreadings folds to one
    folded = []
    for t, h in fixed:
        hit = None
        if not t.startswith("---"):
            ftl = flat(t)
            for k in range(max(0, len(folded) - 3), len(folded)):
                u = folded[k][0]
                ful = flat(u)
                alike = same_doc_line(u, t) or (len(ftl) >= 30 and len(ful) >= 30 and ftl[:24] == ful[:24]
                        and difflib.SequenceMatcher(None, ftl, ful, autojunk=False).ratio() >= 0.55)
                if not u.startswith("---") and alike:
                    hit = k
                    break
        if hit is not None:
            u, uh = folded[hit]
            if (len(norm(t)), t.count("*")) > (len(norm(u)), u.count("*")):
                folded[hit] = (t, h)
            continue
        folded.append((t, h))
    # a short line flush at the left margin, capitalised and unpunctuated,
    # between paragraphs: a heading, drawn one step up
    out = []
    for t, h in folded:
        s = t.strip().strip("*").strip()
        if (h.startswith("<div>") and not h.startswith("<div>&nbsp;") and t == t.strip()
                and 3 <= len(s) <= 45 and s[:1].isupper() and not re.search(r"[.:;,]$", s)
                and not re.match(r"^[*•\-]\s", t.strip()) and " " in s):
            h = '<div class="sn-h2">' + h[len("<div>"):]
        out.append((t, h))
    model.lines = out


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


def _flatmap(s):
    """The text flattened to lowercase letters and digits, with each flat
    character's index back into the original string."""
    out, idx = [], []
    for i, ch in enumerate(s):
        if ch.isalnum():
            out.append(ch.lower())
            idx.append(i)
    return "".join(out), idx


def crumb_same(a, b):
    fa, fb = flat(a), flat(b)
    if not fa or not fb:
        return False
    if fa == fb:
        return True
    if min(len(fa), len(fb)) >= 4 and abs(len(fa) - len(fb)) <= 10 and (fa.startswith(fb) or fb.startswith(fa)):
        return True
    if (min(len(fa), len(fb)) >= 4 and abs(len(fa) - len(fb)) <= 6 and fa[:3] == fb[:3]
            and difflib.SequenceMatcher(None, fa, fb, autojunk=False).ratio() >= 0.7):
        return True
    k = min(len(fa), len(fb))
    return k >= 5 and abs(len(fa) - len(fb)) <= 12 and sum(1 for x, y in zip(fa[:k], fb[:k]) if x != y) <= 1


def chain_paths(paths):
    """Partial readings of one path bar joined: the longest read is the
    spine, and crumbs the other reads carry between its anchors slot in
    where they sat."""
    paths = [p for p in paths if p]
    if not paths:
        return []
    base = list(max(paths, key=len))
    for p in paths:
        if p is base:
            continue
        at = 0                     # insertion point in base
        for c in p:
            j = next((k for k in range(len(base)) if crumb_same(base[k], c)), None)
            if j is not None:
                if len(flat(c)) > len(flat(base[j])):
                    base[j] = c    # the fuller reading of the same crumb
                at = j + 1
            else:
                base.insert(at, c)
                at += 1
    return base


def complete_docs(states):
    """A note cut at a pane's edge, showing whole in another window on the
    same screen (the browser beside Obsidian held the same note wider):
    the cut line takes its tail from the fuller reading, letter for letter."""
    docs = [(st, q["model"]) for st in states for q in st.parts if q["fam"] == "doc"]
    for st, model in docs:
        sources = [(u, h2) for st2, m2 in docs if m2 is not model for u, h2 in m2.lines]
        if not sources:
            continue
        fixed, mended = [], 0
        for t, h in model.lines:
            unfinished = "…</div>" in h or not re.search(r"[.!?:)\u201d\"]$", t.strip())
            if not unfinished or t.startswith("---"):
                fixed.append((t, h, False))
                continue
            t_str = re.sub(r"\s*[:;'\"‘’|_.\]}{@+<>«»]+$", "", t.rstrip())
            if re.search(r"[A-Za-z]{2}\s+[A-Za-z]$", t_str):
                t_str = re.sub(r"\s+[A-Za-z]$", "", t_str)
            if len(t_str) >= 12:
                t = t_str
            ft, _ = _flatmap(t)
            if len(ft) < 16:
                fixed.append((t, h, False))
                continue
            suffix = ft[-14:]
            best = ""
            for u, _h in sources:
                fu, iu = _flatmap(u)
                pos = fu.find(suffix)
                while pos != -1:
                    end = pos + len(suffix)
                    if len(fu) - end >= 8 and end - 1 < len(iu):
                        tail = u[iu[end - 1] + 1:].rstrip()
                        if len(tail) > len(best) and len(tail) <= 220:
                            best = tail
                    pos = fu.find(suffix, pos + 1)
            done = False
            if best:
                t2 = t.rstrip() + best
                h2 = rebuild_line(h, t2)
                if h2 is not None:
                    t, h = t2, h2.replace("…</div>", "</div>") if best.endswith((".", ")", ":")) else h2
                    mended += 1
                    done = True
            fixed.append((t, h, done))
        # a completed line runs on into what the next drawn line already
        # says: the two join at their overlap and read as one
        joined = []
        for row3 in fixed:
            t, h = row3[0], row3[1]
            prev_done = joined and joined[-1][2]
            first_alpha = next((ch for ch in t if ch.isalpha()), "")
            if prev_done and not t.startswith("---") and first_alpha.islower():
                pt, ph = joined[-1][0], joined[-1][1]
                fi, mi = _flatmap(pt)
                fj, mj = _flatmap(t)
                hit = None
                for k in range(14, 7, -1):
                    if len(fi) >= k and len(fj) >= k:
                        p = fj.find(fi[-k:], 0, 90)
                        if p != -1:
                            hit = (k, p)
                            break
                if hit and len(fj) - (hit[1] + hit[0]) >= 6:
                    k, p = hit
                    head = pt[:mi[len(fi) - k]]
                    tail = t[mj[p]:]
                    t2 = head + tail
                    h2 = rebuild_line(ph, t2)
                    if h2 is not None:
                        joined[-1] = (t2, h2, True)
                        mended += 1
                        continue
            joined.append(row3 if len(row3) == 3 else (t, h, False))
        # a continuation line the completed bullet above already carries
        kept2 = []
        for t, h, done in joined:
            if kept2 and not t.startswith("---"):
                fprev = _flatmap(kept2[-1][0])[0]
                fcur = _flatmap(t)[0]
                first_alpha = next((ch for ch in t if ch.isalpha()), "")
                if len(fcur) >= 12 and first_alpha.islower():
                    m = difflib.SequenceMatcher(None, fcur, fprev, autojunk=False)
                    cover = sum(b.size for b in m.get_matching_blocks())
                    if cover >= 0.8 * len(fcur):
                        continue
            kept2.append((t, h, done))
        model.lines = [(t, h) for t, h, _ in kept2]
        if mended:
            st.fine.append(f"{mended} cut lines completed from another reading of the same text")


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
    clean, strong = [], set()
    for st in states:
        if st.title and len(st.title) >= 3 and st.title not in clean:
            clean.append(st.title)
            strong.add(st.title)
        for q in st.parts:
            if q["fam"] == "tree":
                for t, _ in q["model"].lines:
                    n = t.lstrip("│ ˃˅")
                    if len(n) >= 6 and "..." not in n and "…" not in n and n not in clean and " " not in n[:1]:
                        clean.append(n)
            if q["fam"] == "doc":
                dt = q["model"].title()
                if dt and len(dt) >= 4 and dt not in clean:
                    clean.append(dt)
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
                        strong.add(n)

    # one canonical spelling per name: among every reading that flattens
    # alike, the one with the most of its letters intact (capitals, dots,
    # spaces survive OCR worst, so the fullest form is the truest)
    strong_flats = {flat(s) for s in strong}
    # every name any list actually carried: a crumb spelt like one of these
    # is already the folder's own name and must not be grown into a longer
    # one, or a second reading would stretch it again
    row_flats = {flat(r["cells"][0]) for st in states for p in st.parts
                 if isinstance(p["model"], Table) for r in p["model"].rows
                 if r["cells"] and r["cells"][0]}
    strong_names = sorted(strong | {w for w in draw2.SIDEBAR_WORDS if len(w) >= 5}, key=len)
    canon, canon_fold = {}, {}
    def rank_of(c):
        return (sum(1 for ch in c if ch.isupper()), sum(1 for ch in c if not ch.isalnum()), len(c))
    for c in clean + [w for w in draw2.SIDEBAR_WORDS if len(w) >= 5]:
        f = flat(c)
        if canon.get(f) is None or rank_of(c) > rank_of(canon[f]):
            canon[f] = c
        g = fold(f)
        if canon_fold.get(g) is None or rank_of(c) > rank_of(canon_fold[g]):
            canon_fold[g] = c

    # a name read with its dot, space or capital intact anywhere upgrades
    # the barer readings of the same letters ("VaultIndex.md" takes the
    # form "Vault Index" + ".md" once both were seen)
    for f in list(canon):
        if f.endswith("md") and len(f) >= 10:
            base = canon.get(f[:-2])
            if base and len(f[:-2]) >= 8 and not base.lower().endswith(".md"):
                cand = base + ".md"
                if rank_of(cand) > rank_of(canon[f]):
                    canon[f] = cand
                g2 = fold(f)
                if rank_of(cand) > rank_of(canon_fold.get(g2, "")):
                    canon_fold[g2] = cand

    def exact_fix(name):
        f = flat(name)
        cands = [c for c in (canon.get(f), canon_fold.get(fold(f))) if c]
        if not cands and f.endswith("md") and len(f) >= 10:
            base = canon.get(f[:-2])
            if base and len(flat(base)) >= 8 and not base.lower().endswith(".md"):
                cands.append(base + ".md")
        best = max(cands, key=rank_of, default=None)
        if best and best != name and rank_of(best) >= rank_of(name):
            return best
        return None

    def better(name, fuzzy=False):
        f = flat(name)
        if len(f) < 4:
            return None
        b = exact_fix(name)
        if b:
            return b
        if name in strong:
            return None
        for c in clean:
            cf = flat(c)
            if cf + "md" == f or f + "md" == cf:
                continue              # the same name, one read with its .md: not a fuzzy fix
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
        if flat(name) in {flat(c) for c in clean}:
            return None           # a name the pool already holds needs no rescue
        f = re.sub(r"(md|m d)$", "", flat(name))
        if len(f) < 8:
            return None
        scored = sorted(((difflib.SequenceMatcher(None, re.sub(r"md$", "", flat(c)), f, autojunk=False).ratio(), c)
                         for c in clean if len(flat(c)) >= 8 and re.sub(r"md$", "", flat(c)) != f), reverse=True)
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
                        if flat(b) != flat(name):
                            st.fine.append(f"{name} read as {b} in the list")
                        t2 = lead + b
                        fixed.append((t2, h.replace(esc(name), esc(b)) if esc(name) in h else esc(t2)))
                    elif re.search(r"[\\|{}<>@]", name) and "<i>" not in h:
                        st.fine.append(f"{name} was not read cleanly")
                        fixed.append((t, h.replace(esc(name), "<i>" + esc(name) + "</i>")
                                      if esc(name) in h else esc(lead) + "<i>" + esc(name) + "</i>"))
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
                    garbage = " " in n and "_" not in n and "..." not in n
                    b = better(n, fuzzy=doubtful)
                    if not b and (doubtful or garbage) and not any(c for c in r["cells"][1:] if tidy_date(c) or tidy_size(c)):
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
                for path in [table.path] + table.paths:
                    for i, c in enumerate(path):
                        c = mend_numbered(c, strong_names)    # o3 is a nought
                        path[i] = c
                        f = flat(c)
                        b = exact_fix(c)
                        if (not b and len(f) >= 4 and f not in strong_flats
                                and f not in row_flats and canon.get(f, c) == c):
                            # Finder cuts a long crumb short: the folder's
                            # real name is the pool name this crumb opens,
                            # allowing one slip in what was read
                            def opens(p):
                                fp = flat(p)
                                if len(fp) <= len(f) or len(fp) - len(f) > 16:
                                    return False
                                head = fp[:len(f)]
                                return sum(1 for x, y in zip(head, f) if x != y) <= (0 if len(f) < 6 else 1)
                            # only a name read whole somewhere can finish a
                            # crumb, and the shortest such name is the folder
                            # Finder cut short -- a longer one is a different file
                            starts = [p for p in strong_names if opens(p)]
                            exact = [p for p in starts if flat(p).startswith(f)]
                            starts = exact or starts      # a clean opening beats a slipped one
                            if starts:
                                b = min(starts, key=lambda p: len(flat(p)))
                        if b:
                            path[i] = b
                # the crumbs read at different moments chain into the one
                # bar the window carried (each partial read skipped what
                # its engines missed)
                table.path = chain_paths([table.path] + table.paths)
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
                        if ki >= len(r["cells"]) or not r["cells"][ki]:
                            continue
                        if dominant and flat(r["cells"][ki]) == flat(dominant):
                            r["cells"][ki] = dominant
                            if ki < len(r["italic"]):
                                r["italic"][ki] = False
                            continue
                        if kindish.search(r["cells"][ki]):
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
    complete_docs(states)


# ------------------------------------------------------------- the screen itself
#
# A moment picture is the whole screen at the size the video had it: every
# window where it sat, the one being shown filled with what it held over
# that stretch of time, the others as empty outlines. Its content comes
# only from the moments inside the stretch, so it stays an honest still.

def frame_of(m):
    return shapes.frame_of(m)


_CAMPIX = {}


def camera_pic(path, box):
    """The camera's own picture, cut from the frame: the one part of a
    screen no drawing can honestly rebuild."""
    if not path or not box:
        return None
    key = (path, tuple(int(v) for v in box))
    if key in _CAMPIX:
        return _CAMPIX[key]
    uri = None
    try:
        import base64
        import io
        from PIL import Image
        im = Image.open(path).convert("RGB").crop([int(v) for v in box])
        w = min(720, im.width)
        if im.width > w:
            im = im.resize((w, max(1, round(im.height * w / im.width))), Image.BILINEAR)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=70)
        uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        uri = None
    _CAMPIX[key] = uri
    return uri


def box_texts(state):
    """The words that place a window on the screen: the ones of its own
    structure. A list window is placed by its list -- rows, headings, sidebar,
    path -- never by the note showing through behind it, which the reader may
    have filed on the same slice of the screen."""
    t = state.main_table()
    if not t:
        every = state_texts(state)
        return every, every
    out = set()
    strong = set()                # words no other window would share: the
    for r in t.rows:              # rows' names, and the window's own name
        if r["cells"] and r["cells"][0]:
            strong.add(fold(r["cells"][0]))
        for c in r["cells"]:
            out.add(fold(c))
    for c in list(t.header) + list(t.side) + list(t.path) + list(t.bottom):
        out.add(fold(c if isinstance(c, str) else str(c)))
    if state.title:
        out.add(fold(state.title))
        strong.add(fold(state.title))
    out.discard("")
    strong.discard("")
    return out, strong


def state_texts(state):
    """Every word this window itself drew, for telling its own content
    apart from a window behind it read on the same slice of the screen."""
    out = set()
    for part in state.parts:
        model = part["model"]
        if isinstance(model, Table):
            for cell in model.header:
                out.add(fold(cell if isinstance(cell, str) else cell.get("text", "")))
            for row in model.rows:
                for cell in row["cells"]:
                    out.add(fold(cell))
            for s in list(model.side) + list(model.path) + list(model.top):
                out.add(fold(s if isinstance(s, str) else str(s)))
        elif isinstance(model, Lines):
            for text, _ in model.lines:
                out.add(fold(text.strip("│ ˃˅")))
        elif isinstance(model, list):
            for s in model:
                out.add(fold(s if isinstance(s, str) else str(s)))
    out.discard("")
    return out


def snap_rect(items, mine, frame, W, H, strong=None):
    """The real window these words sat in, off the picture of the screen.
    Of every rectangle drawn on the frame, the one this window's own words
    both fill and stay inside; nothing here knows one program from another."""
    boxes = shapes.find(frame) if frame else []
    if not boxes or not mine:
        return None
    best, score_best = None, 0.0
    for r in boxes:
        inside = [it for it in mine
                  if r[0] - 12 <= (it["box"][0] + it["box"][2]) / 2 <= r[2] + 12
                  and r[1] - 12 <= (it["box"][1] + it["box"][3]) / 2 <= r[3] + 12]
        if len(inside) < max(3, 0.25 * len(mine)):
            continue
        share = len(inside) / float(len(mine))
        bb = [min(it["box"][0] for it in inside), min(it["box"][1] for it in inside),
              max(it["box"][2] for it in inside), max(it["box"][3] for it in inside)]
        area = max(1.0, (r[2] - r[0]) * (r[3] - r[1]))
        fill = max(0.0, (bb[2] - bb[0]) * (bb[3] - bb[1])) / area
        score = share * share * (fill ** 0.5)
        if score > score_best:
            best, score_best = r, score
    if best is None or score_best < 0.12:
        return None
    # only words no other window would share may pull the box wider: a
    # header or a path crumb sits identically in two windows of one program
    tell = strong if strong else mine
    inside = [it for it in tell
              if best[0] - 12 <= (it["box"][0] + it["box"][2]) / 2 <= best[2] + 12
              and best[1] - 12 <= (it["box"][1] + it["box"][3]) / 2 <= best[3] + 12]
    share = len(inside) / float(len(tell))
    if share < 0.75:
        # the words run past this rectangle: two windows read as one, or a
        # window wider than its drawn frame. The honest box holds them all.
        bb = [min(it["box"][0] for it in tell), min(it["box"][1] for it in tell),
              max(it["box"][2] for it in tell), max(it["box"][3] for it in tell)]
        return ([min(best[0], bb[0]), min(best[1], bb[1]),
                 min(float(W), max(best[2], bb[2])), min(float(H), max(best[3], bb[3]))], False)
    return ([float(v) for v in best], True)


def settle_rects(state, W, H):
    """A window is sometimes only part-visible -- something is drawn over
    it, or the picture fades. Where one moment's rectangle sits inside
    another's and three of its four sides agree, it is the same window seen
    short, so the fuller shape stands for both."""
    tsx = [t for t in state.rects if t in state.measured]
    for t in tsx:
        r = state.rects[t]
        for u in tsx:
            if u == t:
                continue
            big = state.rects[u]
            if (big[2] - big[0]) * (big[3] - big[1]) <= (r[2] - r[0]) * (r[3] - r[1]):
                continue
            if not (big[0] - 8 <= r[0] and big[1] - 8 <= r[1]
                    and r[2] <= big[2] + 8 and r[3] <= big[3] + 8):
                continue
            near = sum((abs(r[0] - big[0]) <= 0.02 * W, abs(r[2] - big[2]) <= 0.02 * W,
                        abs(r[1] - big[1]) <= 0.02 * H, abs(r[3] - big[3]) <= 0.02 * H))
            if near >= 3:
                state.rects[t] = list(big)
                break


def settle_across(states, order, W, H):
    """The same window carries the same edges from one thing it shows to the
    next. Where a window's rectangle at one moment sits inside the rectangle
    another state of that same window had a moment either side, and three of
    the four sides agree, it is that window seen short and the fuller shape
    stands. Two windows of one program standing side by side never agree on
    three sides, so they stay apart."""
    at = {ts: i for i, ts in enumerate(order)}
    for st in states:
        for ts in list(st.rects):
            r = st.rects[ts]
            i = at.get(ts)
            if i is None:
                continue
            for other in states:
                if other is st or other.name != st.name:
                    continue
                for us, big in other.rects.items():
                    j = at.get(us)
                    if j is None or abs(j - i) > 3 or us not in other.measured:
                        continue
                    if (big[2] - big[0]) * (big[3] - big[1]) <= (r[2] - r[0]) * (r[3] - r[1]):
                        continue
                    if not (big[0] - 8 <= r[0] and big[1] - 8 <= r[1]
                            and r[2] <= big[2] + 8 and r[3] <= big[3] + 8):
                        continue
                    near = sum((abs(r[0] - big[0]) <= 0.02 * W, abs(r[2] - big[2]) <= 0.02 * W,
                                abs(r[1] - big[1]) <= 0.02 * H, abs(r[3] - big[3]) <= 0.02 * H))
                    if near >= 3:
                        st.rects[ts] = list(big)
                        st.measured.add(ts)
                        r = st.rects[ts]


def content_rect(state, group, m):
    """Where the window sat, in frame pixels: the reader's measurement when
    it made one, else the box around the content this window actually drew
    -- words from a window behind, which the reader read on the same pane,
    stay out of it."""
    items = [it for p in group.get("panes") or [] for it in draw2.items_of(p) if it["text"].strip()]
    if not items:
        return list(group.get("rect") or [0, 0, 0, 0])
    W, H = (m.get("size") or [1920, 1080])[:2]
    for w in m.get("windows") or []:
        r = w.get("rect")
        if not r:
            continue
        inside = sum(1 for it in items
                     if r[0] - 20 <= it["box"][0] and it["box"][2] <= r[2] + 20
                     and r[1] - 20 <= it["box"][1] and it["box"][3] <= r[3] + 20)
        if inside >= 0.6 * len(items):
            state.measured.add(m["ts"])
            return [float(v) for v in r]
    rh = max(12.0, (sum(it["box"][3] - it["box"][1] for it in items) / len(items)) * 1.6)
    plain = [min(it["box"][0] for it in items), min(it["box"][1] for it in items),
             max(it["box"][2] for it in items), max(it["box"][3] for it in items)]
    # a window whose words sit where they sat a moment ago has not moved, so
    # its edges are the edges already measured: the picture of the screen is
    # only read again when something about the window actually changed
    was = getattr(state, "_stood", None)
    if was and all(abs(a - b) <= 0.015 * W for a, b in zip(plain[::2], was[0][::2])) \
            and all(abs(a - b) <= 0.015 * H for a, b in zip(plain[1::2], was[0][1::2])):
        if was[2]:
            state.measured.add(m["ts"])
        return list(was[1])
    own, own_strong = box_texts(state)
    mine = [it for it in items if fold(it["text"]) in own] if own else []
    tops = getattr(state, "topwords", None) or []
    if tops:
        # words along the very top of the frame are another window's strip
        # showing over this one; they say nothing about this window's edges
        strip_y = max(t[4] for t in tops) + 0.005 * H
        mine = [it for it in mine if (it["box"][1] + it["box"][3]) / 2 > strip_y] or mine
    strong = [it for it in mine if fold(it["text"]) in own_strong]
    got = snap_rect(items, mine or items, frame_of(m), W, H, strong=strong or None)
    if got:
        drawn, sure = got
        if state.title:
            # the window's name sitting just above the box is its title bar
            tf = fold(state.title)
            caps = [it for it in items if fold(it["text"]) == tf
                    and drawn[0] - 12 <= (it["box"][0] + it["box"][2]) / 2 <= drawn[2] + 12
                    and drawn[1] - 0.08 * H <= it["box"][1] < drawn[1]]
            if caps:
                drawn = [drawn[0], min(it["box"][1] for it in caps) - 0.01 * H,
                         drawn[2], drawn[3]]
        if sure:
            state.measured.add(m["ts"])
        state._stood = (plain, drawn, sure)
        return drawn
    spans = [(q["x0"], q["x1"]) for q in state.parts if q.get("x0") is not None and q.get("x1") is not None]
    if spans:
        xlo = min(a for a, _ in spans) - 2 * rh
        xhi = max(b for _, b in spans) + 2 * rh
        keep = [it for it in items if it["box"][2] > xlo and it["box"][0] < xhi]
        if len(keep) >= 3:
            items = keep
    x0 = min(it["box"][0] for it in items)
    y0 = min(it["box"][1] for it in items)
    x1 = max(it["box"][2] for it in items)
    y1 = max(it["box"][3] for it in items)
    heads = [it for it in items if it["role"] == "head"]
    top_pad = 2.6 * rh if heads else 1.4 * rh
    box = [max(0.0, x0 - 0.7 * rh), max(0.0, y0 - top_pad),
           min(float(W), x1 + 0.7 * rh), min(float(H), y1 + 0.9 * rh)]
    state._stood = (plain, box, False)
    return box


def overlap(a, b):
    """How much of the smaller box the two share, nought to one."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return (w * h) / max(1.0, small)


def span_rect(st, ts):
    """A window's shape at one stretch of time. The reader's own
    measurement stands as it is. Otherwise a window does not shrink because
    less of its text was read at one moment, so readings that start and end
    at the same edges are joined into one shape."""
    here = st.rects.get(ts) or st.rect
    if not here:
        return None
    if ts in getattr(st, "measured", set()):
        return list(here)
    W = max(1.0, max((r[2] for r in st.rects.values()), default=1.0))
    H = max(1.0, max((r[3] for r in st.rects.values()), default=1.0))
    box = list(here)
    for t, other in st.rects.items():
        if t in getattr(st, "measured", set()):
            continue
        if abs(other[0] - here[0]) <= 0.04 * W and abs(other[1] - here[1]) <= 0.04 * H \
                and abs(other[2] - here[2]) <= 0.06 * W:
            box = [min(box[0], other[0]), min(box[1], other[1]),
                   max(box[2], other[2]), max(box[3], other[3])]
    return box


def fingerprint(group):
    """What the window showed at one moment, in a word: the first name in
    its list, or the first line of its document. A change means the window
    scrolled or opened something else, and a new picture begins."""
    for p in sorted(group.get("panes") or [], key=lambda p: (p["box"][1], p["box"][0])):
        d = p.get("data") or {}
        for blk in d.get("blocks") or []:
            for row in blk.get("rows") or []:
                if row and row[0]:
                    return norm(row[0])[:24]
        for r in d.get("rows") or []:
            n = r.get("name") or r.get("text")
            if n:
                return norm(n)[:24]
        for ln in p.get("lines") or []:
            s = ln.strip()
            if s and not s.startswith(("---", "[also", "unsettled")):
                return norm(s)[:24]
    return ""


def state_slice(st, t0, t1):
    """The same window as it stood between two times, built only from the
    moments in that stretch."""
    picked = [(m, g) for m, g in st.pieces if t0 <= m["ts"] <= t1]
    if not picked:
        return None
    m0, g0 = picked[0]
    out = State(g0, m0["ts"])
    for m, g in picked:
        out.absorb(g, m)
        if m["ts"] not in out.times:
            out.times.append(m["ts"])
    out.name, out.title = st.name, st.title
    out.theme = st.theme
    out.title_sure = getattr(st, "title_sure", False)
    out.said = [(ts, s) for ts, s in st.said if t0 <= ts <= t1]
    out.of = st
    return out


def name_fits(short, full_name):
    """The same file, one reading cut shorter: equal flat, or the cut's two
    ends opening and closing the full name."""
    a, b = fold(flat(short)), fold(flat(full_name))
    if a == b:
        return True
    if "..." in short:
        head, _, tail = short.partition("...")
        af, bf = fold(flat(head)), fold(flat(tail))
        return bool(af and bf) and len(af) + len(bf) >= 8 and b.startswith(af) and b.endswith(bf)
    return False


def mend_cells(sl, full):
    """A stretch shows the same window the whole state shows, so what the
    stretch's own frames had mangled or covered is taken from the window's
    settled reading: single cells (a date does not change), the path bar,
    and rows the stretch's list skips BETWEEN rows it holds -- those were
    covered, since the list did not scroll within the stretch. Rows above or
    below the stretch's own are never added: they may be past the fold."""
    ft, st_ = full.main_table(), sl.main_table()
    if not ft or not st_:
        return
    # the path bar: a crumb the stretch read short or wrong takes its spelling
    # from the settled path -- but the stretch keeps its own depth, because a
    # selection deepens the real bar and this stretch may not have had one
    if ft.path and not st_.path:
        st_.path = list(ft.path)
    elif ft.path and st_.path:
        walk, hits = 0, []
        for c in st_.path:
            hit = next((k for k in range(walk, len(ft.path))
                        if name_fits(c, ft.path[k])
                        or (len(flat(c)) >= 4 and fold(flat(ft.path[k])).startswith(fold(flat(c))[:4]))), None)
            if hit is None:
                hits = None
                break
            hits.append(hit)
            walk = hit + 1
        if hits:
            # every settled crumb between the first and last the stretch read:
            # a path bar has no gaps, so the middle fills in; the tail stays
            # the stretch's own, because a selection deepens the real bar
            st_.path = list(ft.path[hits[0]:hits[-1] + 1])
    # the sidebar: fixed furniture, filled in when the stretch saw only part
    if ft.side and st_.side and len(ft.side) > len(st_.side):
        walk = 0
        for w in st_.side:
            hit = next((k for k in range(walk, len(ft.side)) if name_fits(w, ft.side[k])), None)
            if hit is None:
                break
            walk = hit + 1
        else:
            st_.side = list(ft.side)
    # single cells, matched by name even when the stretch read it cut
    fulls = [(r["cells"][0], r) for r in ft.rows if r["cells"] and r["cells"][0]]
    def settled_for(name):
        for n, r in fulls:
            if name_fits(name, n):
                return r
        return None
    for r in st_.rows:
        if not r["cells"] or not r["cells"][0]:
            continue
        fr = settled_for(r["cells"][0])
        if not fr:
            continue
        name = r["cells"][0]
        if "..." in name and fr["cells"] and fr["cells"][0]:
            fn = fr["cells"][0]
            head, _, tail = name.partition("...")
            if fold(flat(name)) != fold(flat(fn)) and len(head) + len(tail) < len(fn):
                r["cells"][0] = fn[:len(head)] + "..." + (fn[len(fn) - len(tail):] if tail else "")
                if r["italic"]:
                    r["italic"][0] = False
        elif fr["cells"] and fr["cells"][0] and name != fr["cells"][0] \
                and fold(flat(name)) == fold(flat(fr["cells"][0])):
            r["cells"][0] = fr["cells"][0]
            if r["italic"]:
                r["italic"][0] = False
        for i, h in enumerate(st_.header):
            if i == 0 or i >= len(r["cells"]):
                continue
            j = ft.header.index(h) if h in ft.header else None
            if j is None or j >= len(fr["cells"]) or not fr["cells"][j]:
                continue
            bad = not r["cells"][i] or (h == "Date Modified" and not tidy_date(r["cells"][i]))
            if bad:
                r["cells"][i] = fr["cells"][j]
                if i < len(r["italic"]):
                    r["italic"][i] = False
    # rows the stretch skips between rows it holds
    if len(st_.rows) >= 2 and st_.header == ft.header:
        idxs, walk, ok = [], 0, True
        for r in st_.rows:
            name = r["cells"][0] if r["cells"] else ""
            hit = next((k for k in range(walk, len(ft.rows))
                        if ft.rows[k]["cells"] and name and name_fits(name, ft.rows[k]["cells"][0])), None)
            if hit is None:
                ok = False
                break
            idxs.append(hit)
            walk = hit + 1
        if ok:
            merged, prev = [], None
            for r, k in zip(st_.rows, idxs):
                if prev is not None and k > prev + 1:
                    for j in range(prev + 1, k):
                        fr = ft.rows[j]
                        merged.append({**fr, "cells": list(fr["cells"]),
                                       "italic": list(fr.get("italic") or []), "band": None})
                merged.append(r)
                prev = k
            for j in range(prev + 1, len(ft.rows)):
                fr = ft.rows[j]
                merged.append({**fr, "cells": list(fr["cells"]),
                               "italic": list(fr.get("italic") or []), "band": None})
            st_.rows = merged


def frag_owner(frag, shown):
    """The window a behind-fragment is a piece of, told by shared lines: the
    note or tree read around another window matches the window that later
    shows it whole."""
    def lines_of(st):
        got = set()
        for q in st.parts:
            model = q["model"]
            texts = ([t for t, _ in model.lines] if hasattr(model, "lines")
                     else [t for t in model if isinstance(t, str)] if isinstance(model, list) else [])
            got |= {flat(t)[:80] for t in texts if len(flat(t)) >= 6}
        return got
    mine = lines_of(frag)
    if not mine:
        return None
    def hits(st):
        theirs = lines_of(st)
        n = 0
        for a in mine:
            if a in theirs:
                n += 1
            elif len(a) >= 10 and any(a in b or b in a for b in theirs):
                n += 1            # a line cut at either end still names its note
        return n
    scored = sorted(((hits(st), st) for st in shown), key=lambda x: -x[0])
    if not scored or scored[0][0] < 3:
        return None
    if len(scored) > 1 and scored[1][0] >= 3:
        return "several"          # pieces of more than one window at once
    return scored[0][1]


def near_windows(states, spans, order):
    """For each stretch, the windows that stood on the screen just before or
    just after it: an outline of each, where it sat at its own nearest
    moment, so a picture shows the desk and not one window alone."""
    at = {ts: i for i, ts in enumerate(order)}
    reach = 3
    out = {}
    for s in spans:
        lo, hi = at.get(s["t0"], 0), at.get(s["t1"], 0)
        near = []
        for st in states:
            if st in s["states"]:
                continue
            mine = [at[t] for t in st.times if t in at]
            if not mine:
                continue
            before = [i for i in mine if i < lo]
            after = [i for i in mine if i > hi]
            pick = None
            if before and lo - max(before) <= reach:
                pick = max(before)
            elif after and min(after) - hi <= reach:
                pick = min(after)
            if pick is None:
                continue
            ts = order[pick]
            box = st.rects.get(ts) or st.rect
            if box:
                near.append((st, list(box), "before" if pick < lo else "after"))
        out[s["t0"] + s["t1"]] = near
    return out


def polish(slice_st, states):
    """A window rebuilt from one stretch of time gets the same reading of
    its words as the window's own full picture: the names settled across
    every moment, so the two never spell the same file two ways."""
    kept = [(st, list(st.fine)) for st in states]
    try:
        harmonise([slice_st] + list(states))
    finally:
        for st, fine in kept:
            st.fine[:] = fine
    return slice_st


def screens(states, moments):
    """The video cut into stretches where the screen stood still: the same
    windows, in the same places, showing the same thing."""
    order = [m["ts"] for m in moments]
    by_ts = {m["ts"]: m for m in moments}
    present = {ts: [] for ts in order}
    for st in states:
        for ts in st.times:
            if ts in present:
                present[ts].append(st)
    marks = {}
    for st in states:
        for m, g in st.pieces:
            marks[(id(st), m["ts"])] = fingerprint(g)
    spans, cur = [], None

    def place(st, ts):
        return st.rects.get(ts) or st.rect or [0, 0, 0, 0]

    for ts in order:
        here = present[ts]
        if not here:
            continue
        key = tuple(sorted(id(s) for s in here))
        rects = {id(s): place(s, ts) for s in here}
        shows = tuple(sorted((id(s), marks.get((id(s), ts), "")) for s in here if marks.get((id(s), ts))))
        def alike(v, w):
            if not v or not w or v == w:
                return True
            return difflib.SequenceMatcher(None, v, w, autojunk=False).ratio() >= 0.6
        # the same window in the same place: the boxes largely agree, so a
        # moment that read less of a window does not count as a new screen
        put = cur and cur["key"] == key and all(overlap(cur["rects"][k], rects[k]) >= 0.7 for k in rects)
        same = (put and all(alike(v, w) for (a, v), (b, w) in zip(cur["shows"], shows) if a == b))
        if same:
            cur["t1"] = ts
            cur["ts"].append(ts)
            cur["shows"] = shows or cur["shows"]
            for k, r in rects.items():                # the window's fullest shape over the stretch
                o = cur["rects"][k]
                cur["rects"][k] = [min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3])]
        else:
            if cur:
                spans.append(cur)
            cur = {"t0": ts, "t1": ts, "ts": [ts], "key": key, "rects": rects,
                   "shows": shows, "states": here, "size": by_ts[ts].get("size") or [1920, 1080]}
    if cur:
        spans.append(cur)
    return spans


def desktop_bar(moments):
    """The menu bar as it stood at each moment -- the program at the front
    changes it -- and the clock reading, which stands until it is read
    again."""
    words_at, clock_at, strip_at = {}, {}, {}
    day = ""
    for m in moments:
        H = (m.get("size") or [0, 2160])[1]
        for p in m.get("panes") or []:
            c = old.clock_in(p)
            if c:
                for r in (p.get("data") or {}).get("readings") or []:
                    dm = re.match(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s?([A-Z][a-z]{2})\s?(\d{1,2})\s*\d{1,2}:\d{2}", (r.get("text") or "").strip())
                    if dm and not day:
                        day = f"{dm.group(1)} {dm.group(2)} {dm.group(3)}"
                clock_at[m["ts"]] = f"{day} {c}".strip() if day else c
            if p["box"][1] > 0.02 * H:
                continue
            # The menu bar is set in the smallest type on the screen, so half
            # its words come back from one engine only. Throwing those away
            # left the bar saying "Obsidian File Edit" where it really said
            # eight menus, so they are kept and marked the way every other
            # one-engine reading in this note is marked.
            strip = [it for it in draw2.items_of(p)
                     if it["box"][1] <= 0.015 * H and it["box"][3] <= 0.035 * H]
            for it in strip:
                if it["ok"] and len(it["text"]) >= 8:
                    strip_at.setdefault(m["ts"], set()).add(it["text"])
            if strip:
                top_it = min(strip, key=lambda it: it["box"][1])
                cy0 = (top_it["box"][1] + top_it["box"][3]) / 2
                h0 = max(1, top_it["box"][3] - top_it["box"][1])
                strip = [it for it in strip if abs((it["box"][1] + it["box"][3]) / 2 - cy0) <= 0.6 * h0]
            here = words_at.setdefault(m["ts"], [])
            for it in sorted(strip, key=lambda it: it["box"][0]):
                w = it["text"]
                if (not old.CLOCK.match(w) and len(w) <= 24 and " " not in w.strip()
                        and not any(same_text(w, x) for x in here)):
                    here.append(w)
    # The bar and the clock stand until they are read again. A bar is read
    # short as often as it is read whole - a word sits under the cursor, or
    # the strip is cut - so a shorter reading of the SAME bar does not
    # replace the fuller one: the two are put together, the way any part of
    # the screen is filled in from the moment it stood clear. Only a
    # different program at the front, which shows as a different first
    # word, starts the bar over.
    last_w, last_c = [], ""
    for m in moments:
        got = words_at.get(m["ts"]) or []
        if len(got) >= 3:
            if last_w and same_text(got[0], last_w[0]):
                merged = list(last_w)
                for w in got:
                    if not any(same_text(w, x) for x in merged):
                        merged.append(w)
                last_w = merged
            else:
                last_w = got
        words_at[m["ts"]] = last_w
        last_c = clock_at.get(m["ts"], last_c)
        if last_c:
            clock_at[m["ts"]] = last_c
    return words_at, clock_at, strip_at


def strip_furniture(st, strip_at):
    """What the frame's own top strip said -- the menu bar, a tab row -- is
    the desk's furniture, not a window's title or a note's first line. The
    bar stands all video, so every moment's strip counts, and a partial strip
    reading still names the line it is part of."""
    tops = {fold(flat(w)) for texts in strip_at.values() for w in texts
            if len(flat(w)) >= 8 and not old.CLOCK.match(w.split()[-1] if w.split() else w)}
    if not tops:
        return
    def furniture(text):
        f = fold(flat(text))
        if len(f) < 8:
            return False
        # a partial strip reading loses its left end, so it survives as the
        # line's tail; a mere substring inside a longer sentence does not count
        return any(f in w or f == w or f.endswith(w) for w in tops)
    if st.title and furniture(st.title):
        st.title = None
    for q in st.parts:
        model = q["model"]
        if q["fam"] not in ("doc", "tree") or not hasattr(model, "lines"):
            continue
        kept = []
        for t, h in model.lines:
            bare = t.strip().strip("#*>\u2502 \u02c3\u02c5").strip()
            if bare and furniture(bare):
                continue
            kept.append((t, h))
        model.lines = kept


def bar_title(st, H):
    """A window title that is really the menu bar read as one string: the
    same words sit in the frame's own top strip."""
    t = st.title
    if not t:
        return False
    for w in getattr(st, "topwords", ()):
        if len(w[0]) < 0.75 * len(t):
            continue              # a scrap of a word proves nothing
        if w[2] <= 0.035 * H and (same_text(t, w[0])
                or (len(t) >= 8 and len(w[0]) >= 8 and (t in w[0] or w[0] in t))):
            return True
    return False


def label_for(st):
    """What to call a window in a picture: its program and what it showed."""
    name = st.name.replace("The ", "").replace(" window", "")
    return f"{name}: {st.title}" if st.title else name


def behind_for(slice_st, span, subject):
    """Windows that never show in full anywhere, drawn where they sat: the
    strip of a window peeking out above another is the usual case."""
    import furnish
    out = []
    strip = furnish.browser_behind(slice_st)
    if strip:
        rect = subject.rects.get(span["t0"]) or subject.rect or [0, 0, 0, 0]
        tops = [t for t in slice_st.topwords]
        if tops:
            W = span["size"][0] if "size" in span else 3840
            H = span["size"][1] if "size" in span else 2160
            y1 = max(rect[1], max(t[4] for t in tops) + 0.02 * H)
            out.append((None, [0, 0, W, y1], strip))
    return out


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
    return st.title or "its name unread"


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
    all_states = build_states(moments)
    bar_at, clock_at, strip_at = desktop_bar(moments)
    if moments:
        H0 = (moments[0].get("size") or [0, 2160])[1]
        for st in all_states:
            strip_furniture(st, strip_at)
            if bar_title(st, H0):
                st.title = None
    states = [st for st in all_states if st.window_html() and not st.fragment()]
    frags = [st for st in all_states if st not in states and st.has_content() and st.rects]
    # a note's big heading is read as large loose words, never as a doc
    # line; when such a reading opens the window's own title, it is the
    # note's heading and stands above everything else
    all_h = sorted(it["box"][3] - it["box"][1]
                   for m in moments for p in m.get("panes") or []
                   for it in draw2.items_of(p) if it["box"][3] > it["box"][1])
    usual_h = all_h[len(all_h) // 2] if all_h else 30.0
    bigs = {}
    for m in moments:
        for p in m.get("panes") or []:
            for it in draw2.items_of(p):
                tall = it["box"][3] - it["box"][1]
                if (it.get("large") or tall >= 1.6 * usual_h) and len(flat(it["text"])) >= 6:
                    bigs.setdefault(fold(flat(it["text"])), []).append(
                        (it["text"].strip(), it["box"], m["ts"]))
    for st in states:
        doc = st.main_doc()
        name = st.title or (doc.title() if doc else "")
        if not doc or not name or not doc.lines:
            continue
        tf = fold(flat(name))
        hit = max((v for key, v in bigs.items() if len(key) >= 6 and tf.startswith(key)),
                  key=lambda v: len(v[0][0]), default=None)
        if not hit:
            continue
        raw = max((r for r, _, _ in hit), key=len)
        hf = fold(flat(raw))
        if any(fold(flat(t)) == hf for t, _ in doc.lines[:4]):
            continue
        doc.lines.insert(0, (raw, f'<div class="sn-h1"><b>{esc(raw)}</b></div>'))
        st._h1_read = [(t_, list(b_)) for _, b_, t_ in hit]
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

    # ------------------------------------------------ the screens, in order
    import furnish
    spans = [s for s in screens(states, moments)
             if any(st in shown for st in s["states"])]

    owner_of = {id(f): frag_owner(f, states) for f in frags}

    # ------- one map of place: every moment's words matched to the richest
    # moment's, so a box measured under one zoom lands rightly under another
    def word_boxes(m):
        seen = {}
        for p in m.get("panes") or []:
            for it in draw2.items_of(p):
                key = fold(flat(it["text"]))
                if len(key) >= 5:
                    seen.setdefault(key, []).append(it["box"])
        return {k: v[0] for k, v in seen.items() if len(v) == 1}

    words_of = {m["ts"]: word_boxes(m) for m in moments}
    base_ts = max(words_of, key=lambda t: len(words_of[t])) if words_of else None
    base_words = words_of.get(base_ts) or {}
    Wf, Hf = (moments[0].get("size") or [1920, 1080])[:2] if moments else (1920, 1080)

    def med(vals):
        vals = sorted(vals)
        return vals[len(vals) // 2]

    def fit_map(ts_list):
        """Scale and shift carrying the base moment's places onto these
        moments, fitted on words read in both. A line read cut still
        anchors the side it kept and votes for the scale by its height."""
        mine = {}
        for t in ts_list:
            for key, b in (words_of.get(t) or {}).items():
                mine.setdefault(key, b)
        exact = [(base_words[key], q) for key, q in mine.items() if key in base_words]
        cuts = []
        for key, q in mine.items():
            if key in base_words or len(key) < 10:
                continue
            cands = [bk for bk in base_words if len(bk) >= 10 and (bk.endswith(key) or key.endswith(bk))]
            if len(cands) == 1:
                cuts.append((base_words[cands[0]], q, "tail"))
                continue
            cands = [bk for bk in base_words if len(bk) >= 10 and (bk.startswith(key) or key.startswith(bk))]
            if len(cands) == 1:
                cuts.append((base_words[cands[0]], q, "head"))
        kv = [(q[2] - q[0]) / max(1.0, p[2] - p[0]) for p, q in exact if p[2] - p[0] >= 8]
        kv += [(q[3] - q[1]) / max(1.0, p[3] - p[1]) for p, q in exact if p[3] - p[1] >= 10]
        kv += [(q[3] - q[1]) / max(1.0, p[3] - p[1]) for p, q, _ in cuts if p[3] - p[1] >= 10]
        if len(kv) < 3:
            return None
        k = med(kv)
        if not 0.4 <= k <= 4.0:
            return None
        xs = [(p[0], q[0]) for p, q in exact] + [(p[2], q[2]) for p, q in exact]
        xs += [(p[2], q[2]) if side == "tail" else (p[0], q[0]) for p, q, side in cuts]
        ys = [(p[1], q[1]) for p, q in exact] + [(p[1], q[1]) for p, q, _ in cuts]
        for _ in range(2):
            dx = med([qx - k * px for px, qx in xs])
            dy = med([qy - k * py for py, qy in ys])
            keep_x = [(px, qx) for px, qx in xs if abs(k * px + dx - qx) < 0.02 * Wf]
            keep_y = [(py, qy) for py, qy in ys if abs(k * py + dy - qy) < 0.02 * Hf]
            if len(keep_x) < 2 or len(keep_y) < 2:
                return None
            done = len(keep_x) == len(xs) and len(keep_y) == len(ys)
            xs, ys = keep_x, keep_y
            if done:
                break
        return (k, dx, dy)

    def onto(T, box):
        k, dx, dy = T
        return [k * box[0] + dx, k * box[1] + dy, k * box[2] + dx, k * box[3] + dy]

    def back(T, box):
        k, dx, dy = T
        return [(box[0] - dx) / k, (box[1] - dy) / k,
                (box[2] - dx) / k, (box[3] - dy) / k]

    def flatT(T):
        return bool(T) and abs(T[0] - 1) < 0.08 and abs(T[1]) < 0.01 * Wf and abs(T[2]) < 0.01 * Hf

    span_T = {s["t0"]: fit_map(s["ts"]) for s in spans}

    home_reads = {}                # state -> every reading's box, carried home
    secs_of = {m["ts"]: m.get("secs", 0) for m in moments}
    for st in states:
        outs = []
        for t, r in st.rects.items():
            if not r or r[2] <= r[0]:
                continue
            s_ = next((x for x in spans if t in x["ts"]), None)
            T = (span_T.get(s_["t0"]) if s_ else None) or fit_map([t])
            if not T:
                continue
            outs.append((secs_of.get(t, 0), back(T, r), T[0]))
        if outs:
            home_reads[id(st)] = outs

    def home_at(st, t0):
        """Where this window stood around that time. Readings of a standing
        window agree and complete each other; a window that moved forms
        another cluster, and the nearest in time is the one drawn. A box
        carried over from a zoomed view is only trusted to widen the story
        when no straight-on reading exists."""
        outs = home_reads.get(id(st))
        if not outs:
            return None
        want = secs_of.get(t0, 0)

        def iou(a, b):
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[3], b[3]) - max(a[1], b[1])
            if w <= 0 or h <= 0:
                return 0.0
            inter = w * h
            au = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
            return inter / max(1.0, au)

        clusters = []              # [members], each member (sec, rect, k)
        for mem in sorted(outs):
            r = mem[1]
            for c in clusters:
                u = c[0]
                near = sum(1 for i in range(4)
                           if abs(r[i] - u[i]) < 0.03 * (Wf if i % 2 == 0 else Hf))
                if iou(r, u) > 0.5 or (near >= 2 and overlap(r, u) > 0.6):
                    c[0] = [min(u[0], r[0]), min(u[1], r[1]),
                            max(u[2], r[2]), max(u[3], r[3])]
                    c[1].append(mem)
                    break
            else:
                clusters.append([list(r), [mem]])
        best = min(clusters, key=lambda c: min(abs(m[0] - want) for m in c[1]))
        flatly = [m for m in best[1] if abs(m[2] - 1.0) <= 0.15]
        take = flatly or best[1]
        return [min(m[1][0] for m in take), min(m[1][1] for m in take),
                max(m[1][2] for m in take), max(m[1][3] for m in take)]

    own_words = {id(st): {flat(w) for w in box_texts(st)[1] if len(flat(w)) >= 8}
                 for st in states}
    bar_seen = set()               # moments whose own top strip held readings
    for m in moments:
        n = 0
        for p in m.get("panes") or []:
            if p["box"][1] > 0.02 * Hf:
                continue
            for it in draw2.items_of(p):
                if it["box"][1] <= 0.01 * Hf and it["box"][3] <= 0.03 * Hf and len(it["text"]) >= 3:
                    n += 1
        if n >= 2:
            bar_seen.add(m["ts"])
    reach = {id(st): (min(st.times), max(st.times)) for st in states if st.times}
    for f in frags:
        own = owner_of.get(id(f))
        if own is None or own == "several" or not f.times:
            continue
        lo1, hi1 = reach.get(id(own), (min(f.times), max(f.times)))
        reach[id(own)] = (min(lo1, min(f.times)), max(hi1, max(f.times)))
    heights = sorted(b[3] - b[1] for b in base_words.values())
    if heights:
        ui = heights[len(heights) // 4] * furnish.CANVAS_W / max(1, Wf)
        furnish.UI_TXT = min(16.0, max(5.0, ui))

    for st in states:
        for t_, b_ in getattr(st, "_h1_read", ()):
            s_ = next((x for x in spans if t_ in x["ts"]), None)
            T_ = (span_T.get(s_["t0"]) if s_ else None) or fit_map([t_])
            hb = home_at(st, t_)
            if not T_ or not hb:
                continue
            # the note's heading stands well below the window's top edge;
            # the drawn note takes the same top room, span pictures only
            pad_home = back(T_, b_)[1] - hb[1]
            pad_css = pad_home * furnish.CANVAS_W / Wf * furnish.CSS_TXT / furnish.UI_TXT - 60
            if pad_css > 12:
                st._doc_pad = round(pad_css)
            break

    def ghost_list(s, sub_states, carded):
        got = []
        for f in frags:
            ts = next((t for t in s["ts"] if t in f.rects), None)
            if ts is None:
                continue
            own = owner_of.get(id(f))
            if own is not None and own != "several" and (own in sub_states or id(own) in carded):
                continue
            got.append((list(f.rects[ts]), "a window behind", "behind"))
        return got
    if spans:
        parts += ["## Where the windows stood, moment by moment", "",
                  "Where everything stood, and nothing more. Each picture is the shape of the screen over that stretch of "
                  "time: the desktop bar with its own words along the top, and every window outlined where it stood, "
                  "at the size it was, named. The window the stretch is about is the one drawn brightest. Nothing is "
                  "filled in here and no photograph is ever pasted in -- where the camera covered the screen, that "
                  "corner is outlined and said. Every window's content is drawn below, large enough to read. A stretch "
                  "covers several timestamps whenever the screen stood still, and the stamp in the corner says which; "
                  "where the reader measured a window's edges those are the edges drawn, otherwise they are taken from "
                  "where that window's own words sat.", ""]
        last_T = None
        for s in spans:
            subjects = []
            for st in s["states"]:
                if st not in shown:
                    continue
                sl = state_slice(st, s["t0"], s["t1"]) or st
                if sl is not st:
                    # the desk's chrome stands all video; a stretch that did
                    # not re-read it still lives under it
                    sl.topwords = sl.topwords + [t for t in st.topwords
                                                 if not any(same_text(t[0], u[0]) for u in sl.topwords)]
                    polish(sl, states)
                    drop_guessed([sl])
                    mend_cells(sl, st)
                    strip_furniture(sl, strip_at)
                    if bar_title(sl, s["size"][1]):
                        sl.title = None
                    sl.title = sl.title or st.title
                    fd, sd = st.main_doc(), sl.main_doc()
                    if fd and sd and fd.lines and sd.lines is not fd.lines \
                            and "sn-h1" in fd.lines[0][1] and not any(
                                fold(flat(t)) == fold(flat(fd.lines[0][0])) for t, _ in sd.lines[:3]):
                        sd.lines.insert(0, fd.lines[0])
                sl._doc_pad = getattr(st, "_doc_pad", 0)
                sl.rects, sl.measured = st.rects, st.measured
                shape = s["rects"].get(id(st)) or span_rect(st, s["t0"]) or st.rect
                sl.rect = shape
                if sl.has_content() and shape:
                    subjects.append((st, sl, shape))
            if not subjects:
                continue
            # deepest first: the bigger window lies under the smaller one
            subjects.sort(key=lambda x: -(x[2][2] - x[2][0]) * (x[2][3] - x[2][1]))
            # the windows truly behind, their own content where it sat: told
            # by a fragment read around the front windows, or by another
            # window's note or tree filed onto a front window's own panes
            sub_states = [stx for stx, _, _ in subjects]
            T = span_T.get(s["t0"])
            if T is None:
                T = last_T          # nothing readable moved between the two
            last_T = T
            bar_words = max((bar_at[t] for t in s["ts"] if bar_at.get(t)),
                            key=len, default=[])
            clock = next((clock_at[t] for t in s["ts"] if clock_at.get(t)), "")
            barred = any(t in bar_seen for t in s["ts"])

            kz_now = T[0] if T else 1.0
            S_now = max(0.05, kz_now * furnish.UI_TXT / furnish.CSS_TXT)

            def span_pad(st_, top):
                seen = next((b_ for t_, b_ in getattr(st_, "_h1_read", ())
                             if t_ in s["ts"]), None)
                if seen is None:
                    return getattr(st_, "_doc_pad", 0)
                pad = (seen[1] - top) * furnish.CANVAS_W / Wf / S_now - 60
                return round(pad) if pad > 12 else 0

            for stx, sl, shape in subjects:
                sl._doc_pad = span_pad(stx, shape[1])

            # which windows behind were read through or around the front ones
            seen_here = set()
            for f in frags:
                if any(t in f.rects for t in s["ts"]):
                    own = owner_of.get(id(f))
                    if own is not None and own != "several":
                        seen_here.add(id(own))
            import types
            for stx, sl, _ in subjects:
                keep = set() if stx.main_table() else {id(stx.tree()), id(stx.main_doc())}
                for q in stx.parts:
                    if q["fam"] in ("doc", "tree") and id(q["model"]) not in keep:
                        own = frag_owner(types.SimpleNamespace(parts=[q]),
                                         [o for o in states if o is not stx])
                        if own is not None and own != "several":
                            seen_here.add(id(own))

            # every other window this stretch's frame still shows, drawn
            # whole where its zoom put it; the screen's edge cuts the rest
            behinds, carded = [], set()
            lo, hi = s["t0"], s["t1"]
            for own in states:
                if own in sub_states or id(own) in carded or T is None:
                    continue
                hb = home_at(own, s["t0"])
                if hb is None:
                    continue
                box = onto(T, hb)
                # a long line of its own text read this stretch places the
                # window more surely than any carried box
                keys = own_words.get(id(own)) or set()
                long_hits = []
                for t in s["ts"]:
                    for key, b in (words_of.get(t) or {}).items():
                        if len(key) >= 12 and (key in keys or any(
                                key in sk or sk in key for sk in keys)):
                            long_hits.append(b)
                for b in long_hits:
                    box = [min(box[0], b[0]), min(box[1], b[1]),
                           max(box[2], b[2]), max(box[3], b[3])]
                vw = min(box[2], Wf) - max(box[0], 0.0)
                vh = min(box[3], Hf) - max(box[1], 0.0)
                if vw < 0.04 * Wf or vh < 0.04 * Hf:
                    continue
                # the same physical window navigated on: its old view sits
                # exactly under a front window and is not on the screen
                if any(r and overlap(box, r) * min((r[2] - r[0]) * (r[3] - r[1]),
                                                   (box[2] - box[0]) * (box[3] - box[1]))
                       > 0.6 * (box[2] - box[0]) * (box[3] - box[1])
                       for _, _, r in subjects):
                    continue
                lo1, hi1 = reach.get(id(own), ("", ""))
                alive = (id(own) in seen_here or len(long_hits) >= 2
                         or (lo1 and lo1 <= lo and hi <= hi1))
                if not alive:
                    # its own words read inside its place this stretch
                    px, py = 0.02 * Wf, 0.02 * Hf
                    hits, open_hits = 0, 0
                    fronts = [r for _, _, r in subjects if r]
                    for t in s["ts"]:
                        for key, b in (words_of.get(t) or {}).items():
                            if not (box[0] - px <= b[0] and b[2] <= box[2] + px
                                    and box[1] - py <= b[1] and b[3] <= box[3] + py):
                                continue
                            if key in keys or (len(key) >= 12 and any(
                                    key in sk or sk in key for sk in keys)):
                                hits += 1
                            # a word standing where NO window in front stood:
                            # something was showing there, and this window's
                            # own place is what covers it. A file list says
                            # "55 bytes" and "Folder" like every other, so
                            # asking for its own turn of phrase loses windows
                            # that are plainly in view down an edge.
                            elif not any(r[0] - px <= (b[0] + b[2]) / 2 <= r[2] + px
                                         and r[1] - py <= (b[1] + b[3]) / 2 <= r[3] + py
                                         for r in fronts):
                                open_hits += 1
                    if hits < 2 and open_hits < 8:
                        if os.environ.get("UIX_WHY") == s["t0"]:
                            print(f"   dropped {label_for(own)!r} box "
                                  f"{[round(v) for v in box]} hits {hits} "
                                  f"long {len(long_hits)} reach {reach.get(id(own))}",
                                  file=sys.stderr)
                        continue
                carded.add(id(own))
                if os.environ.get("UIX_WHY") == s["t0"]:
                    print(f"   drawn {label_for(own)!r} box {[round(v) for v in box]}",
                          file=sys.stderr)
                behinds.append((label_for(own), list(box)))
            behinds.sort(key=lambda hb: -(hb[1][2] - hb[1][0]) * (hb[1][3] - hb[1][1]))
            if barred:
                for stx, sl, _ in subjects:
                    strip = behind_for(sl, dict(s, size=s["size"]), stx)
                    if strip:
                        behinds.append(("the browser, behind", strip[0][1]))
                        break
            m_t0 = next((mm for mm in moments if mm["ts"] == s["t0"]), None)
            cam = shapes.camera_box(frame_of(m_t0)) if m_t0 else None
            cam_pic = None   # a camera picture is never pasted in; it is outlined
            head = f"### {s['t0']}" + ("" if s["t0"] == s["t1"] else f" to {s['t1']}") + \
                   " - " + " \u00b7 ".join(label_for(st) for st, _, _ in subjects)
            parts += [head, ""]
            for stx, sl, _ in subjects:
                sl._label = label_for(stx)
            parts.append(furnish.screen_shot(
                {"t0": s["t0"], "t1": s["t1"]},
                [(sl, shape) for _, sl, shape in subjects],
                s["size"][0], s["size"][1],
                bar_words if barred else None, clock if barred else "",
                behind_cards=behinds,
                ghosts=ghost_list(s, sub_states, carded),
                camera=(cam, cam_pic) if cam else None,
                sure=all(any(t in st.measured for t in s["ts"]) for st, _, _ in subjects),
                kz=(T[0] if T else 1.0)))
            parts.append("")
            seen_said = set()
            for _, sl, _ in subjects:
                for ln in sl.said_html():
                    if ln not in seen_said:
                        seen_said.add(ln)
                        parts += [ln, ""]
        parts += ["---", ""]

    parts += ["## Every window, rebuilt to read", "",
              "Every window rebuilt, large enough to read: the toolbar, the sidebar, the rows with their dates and "
              "sizes, the path bar, the note's own text -- drawn from what was read off the screen, holding everything "
              "gathered across every moment that window showed the same thing. This is the content; the pictures above "
              "only say where each of these stood.", ""]
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
    # the desktop bar stands in the screen pictures themselves; saying it
    # again at the end is the same fact twice

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
