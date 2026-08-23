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


def stitch(old_items, new_items, key):
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
    for j, n in enumerate(new_items):
        for i, o in enumerate(old_items):
            if same_text(key(o), key(n)):
                pairs.append((i, j))
                break
    if not pairs:
        return old_items + list(new_items)
    out = list(old_items)
    # walk the new run; unmatched items go after their nearest matched
    # predecessor's twin
    last_old = -1
    insert_at = {}
    matched = dict(pairs)           # new index -> old index
    pos = {}
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


class Table:
    def __init__(self):
        self.header = []
        self.rows = []          # each: {"cells": [...], "band": hue, "italic": [bool]}
        self.side = []
        self.top = []
        self.path = []
        self.bottom = []
        self.banded_names = set()

    def add(self, built):
        top, side, head, rows, bottom, _ = built
        if head and (not self.header or len(head) > len(self.header)):
            self.header = list(head)
        new_rows = []
        for cells, icon, band in rows:
            plain = [c.replace("*", "") for c in cells]
            italics = [c.startswith("*") and c.endswith("*") and len(c) > 2 for c in cells]
            new_rows.append({"cells": plain, "italic": italics, "band": band})
        self.rows = stitch(self.rows, new_rows, key=lambda r: r["cells"][0] if r["cells"] else "")
        for it in sorted(side, key=lambda it: it["box"][1]):
            t = it["text"]
            if not any(same_text(t, s) for s in self.side):
                self.side.append(t)
        for it in sorted(top, key=lambda it: it["box"][0]):
            t = it["text"]
            if not any(same_text(t, s) for s in self.top):
                self.top.append(t)
        rows_below = draw2.reading_order([it for it in bottom if it["ok"]], lambda it: it["box"])
        best = []
        for row in rows_below:
            # the path is the leading run of crumbs on a row; words after
            # it are the window behind showing through
            run = []
            for it in row:
                if draw2.crumb_like(it["text"]):
                    run.append(it["text"].rstrip(">").strip())
                else:
                    break
            if len(run) >= 2 and len(run) > len(best):
                best = run
            for it in row[len(run):]:
                if it["text"] not in self.bottom:
                    self.bottom.append(it["text"])
        if len(best) >= len(self.path):
            self.path = best

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


class Lines:
    """A tree or a document, as lines that grow when the pane scrolls."""
    def __init__(self, kind):
        self.kind = kind
        self.lines = []         # (text, html)

    def add(self, pairs):
        self.lines = stitch(self.lines, list(pairs), key=lambda p: p[0])

    def identity(self):
        """The first stretch of the text, marks stripped: a note is the same
        note when this reads alike, whatever rank the reader gave a line."""
        body = [t.strip("#*> ") for t, _ in self.lines if t.strip() and not t.startswith("---")]
        return norm(" ".join(body))[:240]


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
            props.append(s)
            continue
        h = old.doc_line(raw, fine)
        if h is None or not s:
            continue
        text = re.split(r"\s+<- ", raw.rstrip())[0].strip()
        out.append((text, h))
    return out, fine


# ------------------------------------------------------------- states

GENERIC = {"macintoshhd", "users", "documents", "jaredr", "jaredrhodenizer", "jaredrhodenize"}

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
            part = self.part_for(k, slot)
            part["x0"] = p["box"][0] if part["x0"] is None else min(part["x0"], p["box"][0])
            part["x1"] = p["box"][2] if part["x1"] is None else max(part["x1"], p["box"][2])
            if k == "a list of columns":
                built = draw2.build_table(p)
                if built:
                    part["model"].add(built)
            elif k == "a file tree":
                pairs, fine = tree_pairs(p)
                part["model"].add(pairs)
                self.fine.extend(fine)
            elif k == "an open document":
                pairs, fine = doc_pairs(p)
                part["model"].add(pairs)
                self.fine.extend(fine)
            elif k in ("a terminal", "a chat log"):
                pairs = [(ln, esc(ln)) for ln in old.content_lines(p) if ln.strip()]
                part["model"].add(pairs)
            else:
                built = draw2.table_from_loose(p)
                if built:
                    # a list the reader left loose: its table, rebuilt
                    self.parts.remove(part)
                    tpart = self.part_for("a list of columns", slot)
                    tpart["x0"], tpart["x1"] = p["box"][0], p["box"][2]
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
        if m["ts"] not in self.times:
            self.times.append(m["ts"])
        table = self.main_table()
        if not self.title and table:
            # the folder's name: the title-bar word that is also a crumb of
            # the path (Finder's title is the folder shown; the path's last
            # crumb may be the selection), else the path's last crumb
            tops = [t for t in table.top if not re.fullmatch(r"[0O]+", t) and len(t) >= 3]
            hit = None
            for c in reversed(table.path):
                hit = next((t for t in tops if same_text(t, c) or norm(t).startswith(norm(c))), None)
                if hit:
                    break
            end = table.path[-1] if table.path else ""
            if hit:
                self.title = hit
            elif end and norm(end) not in GENERIC:
                self.title = end

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
        return bool(t) and not self.title and len(t.rows) < 3 and not others

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
                return False
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
            x, y = da.identity(), db.identity()
            return x == y or difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.75
        if da or db:
            return False
        ra, rb = self.tree(), other.tree()
        if ra and rb:
            return difflib.SequenceMatcher(None, ra.identity(), rb.identity(), autojunk=False).ratio() >= 0.8
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
        table = self.main_table()
        side_words, top_words, path, bottom = [], [], [], []
        if table:
            side_words, top_words, path, bottom = list(table.side), list(table.top), list(table.path), list(table.bottom)
        cols = []       # (html, width in frame pixels)
        for q in self.parts:
            fam, model = q["fam"], q["model"]
            width = max(1, (q["x1"] or 0) - (q["x0"] or 0))
            if fam == "table":
                cols.append(('<div class="sn-body">' + model.html() + "</div>", width))
            elif fam == "tree":
                cols.append(('<div class="sn-tree">' + "\n".join(h for _, h in model.lines) + "</div>", width))
            elif fam == "doc":
                cols.append(('<div class="sn-doc">' + "".join(h for _, h in model.lines) + "</div>", width))
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
        tops = [w for w in top_words if w != self.title and not re.fullmatch(r"[0O]+", w)]
        if self.title or tops:
            t = f"<b>{esc(self.title)}</b> " if self.title else ""
            title_bar = '<div class="sn-titlebar">' + t + " &nbsp; ".join(esc(w) for w in tops) + "</div>"
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
            cands = ([here] if here else []) + [st for st in reversed(states) if st.name == window_name(g["name"]) and st is not here]
            cur = None
            if here and all_repeat:
                cur = here
            else:
                cur = next((c for c in cands if c.same_thing(probe)), None)
            if cur is not None:
                if not all_repeat:
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
    return states


def desktop(moments):
    """The menu bar's words, read along the top strip of the frame, and the
    clock from the first reading to the last."""
    menubar, clocks = [], []
    for m in moments:
        H = (m.get("size") or [0, 0])[1]
        for p in m.get("panes") or []:
            c = old.clock_in(p)
            if c and (not clocks or clocks[-1][1] != c):
                clocks.append((m["ts"], c))
            if p["kind"] != "text, not a tree" or p["box"][1] > 0.02 * H:
                continue
            strip = [it for it in draw2.items_of(p) if it["ok"] and it["box"][3] <= 0.025 * H]
            for it in sorted(strip, key=lambda it: it["box"][0]):
                w = it["text"]
                if not old.CLOCK.match(w) and not any(same_text(w, x) for x in menubar) and len(w) <= 24:
                    menubar.append(w)
    if not (menubar or clocks):
        return []
    right = ""
    if clocks:
        right = clocks[0][1] + (f" → {clocks[-1][1]}" if clocks[-1][1] != clocks[0][1] else "")
    return ["## The desktop", "",
            '<div class="sn-menubar"><span>' + " &nbsp; ".join(esc(w) for w in menubar[:12]) + f"</span><span>{esc(right)}</span></div>", ""]


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
        latest = sts[-1]
        earlier = sts[:-1]
        parts.append(f"## {w} - as at {span_of(latest)}" + (f", {latest.title}" if latest.title else ""))
        parts.append("")
        parts.append(latest.window_html())
        parts.append("")
        for ln in latest.said_html():
            parts.append(ln)
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
