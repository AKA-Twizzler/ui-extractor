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
        items = sorted(bottom, key=lambda it: (round(it["box"][1] / 10), it["box"][0]))
        crumbs = [it["text"].rstrip(">").strip() for it in items if draw2.crumb_like(it["text"]) and it["ok"]]
        if len(crumbs) >= 2 and len(crumbs) >= len(self.path):
            self.path = crumbs
        for it in items:
            if not draw2.crumb_like(it["text"]) and it["ok"] and it["text"] not in self.bottom:
                self.bottom.append(it["text"])

    def identity(self):
        """What folder the list shows: the path's last crumb, else its
        first rows."""
        if self.path:
            return norm(self.path[-1])
        return norm(" ".join(r["cells"][0] for r in self.rows[:3] if r["cells"]))

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
        if self.kind == "an open document":
            body = [t for t, _ in self.lines if t.strip() and t.strip() != "---" and not re.match(r"^[a-z_ ]+: ", t.strip())]
            heads = [t for t in body if t.lstrip().startswith("#")]
            pick = heads[0] if heads else (body[0] if body else "")
            return norm(pick.strip("#* "))[:40]
        return norm(" ".join(t for t, _ in self.lines[:3]))


# ------------------------------------------------------------- pane -> content

def tree_pairs(pane):
    d = pane.get("data") or {}
    out, fine = [], []
    for r in d.get("rows") or []:
        ch = {"right": "˃ ", "down": "˅ "}.get(r.get("chevron"), "  ")
        name = r.get("name") or r.get("raw") or ""
        text = "  " * int(r.get("depth", 0)) + ch + name
        h = esc(text)
        if r.get("band"):
            h = f'<span class="sn-{r["band"]}" style="font-weight:600">{h}</span>'
        out.append((text, h))
        if r.get("name_status") == "uncertain" and r.get("name_second"):
            fine.append(f"{name} / {r['name_second']}")
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

class State:
    def __init__(self, group, ts):
        self.name = group["name"]
        self.title = group.get("title")
        self.rect = group["rect"]
        self.where = group.get("where")
        self.times = [ts]
        self.table = None
        self.tree = None
        self.doc = None
        self.words = []         # (label, [words]) loose strips
        self.term = None
        self.fine = []
        self.said = []          # (ts, text)
        self.theme = None
        self.key = None

    def absorb(self, group, m):
        """Take the group's panes into this state's content."""
        W = (m.get("size") or [1920])[0]
        rect = group["rect"]
        for p in sorted(group["panes"], key=lambda p: (p["box"][0], p["box"][1])):
            if p.get("since") or p.get("same_as"):
                continue
            k = p["kind"]
            if k == "a list of columns":
                built = draw2.build_table(p)
                if built:
                    self.table = self.table or Table()
                    self.table.add(built)
            elif k == "a file tree":
                pairs, fine = tree_pairs(p)
                self.tree = self.tree or Lines(k)
                self.tree.add(pairs)
                self.fine.extend(fine)
            elif k == "an open document":
                pairs, fine = doc_pairs(p)
                self.doc = self.doc or Lines(k)
                self.doc.add(pairs)
                self.fine.extend(fine)
            elif k in ("a terminal", "a chat log"):
                pairs = [(ln, esc(ln)) for ln in old.content_lines(p) if ln.strip()]
                self.term = self.term or Lines(k)
                self.term.add(pairs)
            else:
                lines, fine = draw2.block_loose(p, rect)
                self.fine.extend(fine)
                for ln in lines:
                    label, _, rest = ln.partition(":** ")
                    label = label.strip("* ") if rest else "words"
                    words = [w.strip() for w in (rest or ln).replace(" &nbsp; ", " · ").split(" · ") if w.strip()]
                    home = next((w for w in self.words if w[0] == label), None)
                    if home is None:
                        self.words.append((label, words))
                    else:
                        for w in words:
                            if not any(same_text(w, x) for x in home[1]):
                                home[1].append(w)
        th = old.theme_of(group["panes"])
        self.theme = self.theme or th
        if m["ts"] not in self.times:
            self.times.append(m["ts"])
        if not self.title:
            if self.table and self.table.path:
                self.title = self.table.path[-1]
        self.key = self.identity()

    def identity(self):
        parts = [norm(self.name)]
        if self.table:
            parts.append("list:" + self.table.identity())
        if self.doc:
            parts.append("doc:" + self.doc.identity())
        elif self.tree:
            parts.append("tree:" + self.tree.identity()[:30])
        return "|".join(parts)

    def same_thing(self, other_key):
        """The same window showing the same thing: the list's folder, the
        note's title; a tree alone is judged by likeness of its first rows."""
        a, b = self.key, other_key
        if a == b:
            return True
        ta, tb = a.split("|", 1), b.split("|", 1)
        if ta[0] != tb[0] or len(ta) < 2 or len(tb) < 2:
            return False
        return difflib.SequenceMatcher(None, ta[1], tb[1], autojunk=False).ratio() >= 0.8

    # --------------------------------------------------------- the drawing

    def heading(self):
        span = self.times[0] if len(self.times) == 1 else f"{self.times[0]} to {self.times[-1]}"
        what = f", {self.title}" if self.title else ""
        return f"## {self.name}{what} - as at {span}"

    def window_html(self):
        side_html = ""
        side_words = []
        if self.table and self.table.side:
            side_words = self.table.side
        for label, words in self.words:
            if label in ("Sidebar",) and not side_words:
                side_words = words
        if side_words:
            side_html = '<div class="sn-side">' + "<br>".join(esc(w) for w in side_words) + "</div>"
        main = []
        top_words = (self.table.top if self.table else [])
        for label, words in self.words:
            if label == "Toolbar":
                top_words = top_words + [w for w in words if w not in top_words]
        title_bar = ""
        if self.title or top_words:
            t = f"<b>{esc(self.title)}</b> " if self.title else ""
            title_bar = '<div class="sn-titlebar">' + t + " &nbsp; ".join(esc(w) for w in top_words if w != self.title) + "</div>"
        if self.tree:
            main.append('<div class="sn-tree">' + "\n".join(h for _, h in self.tree.lines) + "</div>")
        if self.table:
            main.append('<div class="sn-body">' + self.table.html() + "</div>")
        if self.doc:
            main.append('<div class="sn-doc">' + "".join(h for _, h in self.doc.lines) + "</div>")
        if self.term:
            main.append('<div class="sn-tree">' + "\n".join(h for _, h in self.term.lines) + "</div>")
        extra = []
        for label, words in self.words:
            if label in ("Sidebar", "Toolbar") and (side_words is words or label == "Toolbar"):
                continue
            if label == "Sidebar":
                continue
            extra.append(f"<div class=\"sn-body\"><b>{esc(label)}:</b> " + " &nbsp;·&nbsp; ".join(esc(w) for w in words) + "</div>")
        foot = ""
        if self.table and self.table.path:
            foot = '<div class="sn-pathbar">' + "›".join(f"<span>{esc(c)}</span>" for c in self.table.path) + "</div>"
        elif self.table and self.table.bottom:
            foot = '<div class="sn-pathbar">' + " &nbsp;·&nbsp; ".join(esc(w) for w in self.table.bottom) + "</div>"
        if self.tree and (self.doc or self.table):
            cols = '<div class="sn-cols sn-wide-left">' + main[0] + "".join(main[1:]) + "</div>"
            body = cols
        elif side_html:
            body = '<div class="sn-cols">' + side_html + "".join(main) + "</div>"
        else:
            body = "".join(main)
        if not (main or side_html):
            return ""
        cls = "sn-window sn-dark" if self.theme == "dark" else "sn-window"
        return f'<div class="{cls}">{title_bar}{body}{"".join(extra)}{foot}</div>'

    def said_html(self):
        out = []
        for ts, text in self.said:
            text = text.strip()
            if not text:
                continue
            if len(text) > LONG_SAID:
                out.append(f"> [!quote]- Jared, {ts} ({len(text.split())} words)\n> {text}")
            else:
                out.append(f'Jared, {ts}: "{text}"')
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
    open_by_name = {}          # window name -> its current state
    for m in moments:
        groups = draw2.window_groups(m)
        seen_names = set()
        for g in groups:
            probe = State(g, m["ts"])
            probe.absorb(g, m)
            if not (probe.table or probe.tree or probe.doc or probe.term or probe.words):
                continue
            cur = open_by_name.get(g["name"])
            all_repeat = all(p.get("since") or p.get("same_as") for p in g["panes"])
            if cur is not None and (all_repeat or cur.same_thing(probe.key)):
                if not all_repeat:
                    cur.absorb(g, m)
                elif m["ts"] not in cur.times:
                    cur.times.append(m["ts"])
                st = cur
            else:
                st = probe
                states.append(st)
                open_by_name[g["name"]] = st
            seen_names.add(g["name"])
        said = (m.get("said") or "").strip()
        if said:
            # the words go under the window that was the moment's subject:
            # the biggest state touched this moment
            touched = [open_by_name[n] for n in seen_names if n in open_by_name]
            if touched:
                home = max(touched, key=lambda s: (s.rect[2] - s.rect[0]) * (s.rect[3] - s.rect[1]))
                home.said.append((m["ts"], said))
    return states


def desktop(moments):
    menubar, clocks = [], []
    for m in moments:
        H = (m.get("size") or [0, 0])[1]
        for p in m.get("panes") or []:
            c = old.clock_in(p)
            if c and (not clocks or clocks[-1][1] != c):
                clocks.append((m["ts"], c))
            if p.get("wi") is None and old.is_menubar(p, H) and p["kind"] == "text, not a tree":
                sure, _, _ = old.split_loose(p)
                for _, t in sure:
                    for w in t.split(" | "):
                        w = w.strip()
                        if w and not old.CLOCK.match(w) and w not in menubar:
                            menubar.append(w)
    if not (menubar or clocks):
        return []
    right = ""
    if clocks:
        right = clocks[0][1] + (f" → {clocks[-1][1]}" if clocks[-1][1] != clocks[0][1] else "")
    parts = ["## The desktop", "",
             '<div class="sn-menubar"><span>' + " &nbsp; ".join(esc(w) for w in menubar) + f"</span><span>{esc(right)}</span></div>"]
    if len(clocks) > 1:
        parts += ["", '<span class="sn-fine">the desktop clock: ' + "; ".join(f"{c} at {ts}" for ts, c in clocks) + "</span>"]
    return parts


def note(records_path, diary_text=None):
    header, moments, footer = old.load(records_path)
    title = header.get("title") or os.path.basename(os.path.dirname(records_path))
    diary_text = diary_text if diary_text is not None else old.diary(records_path)
    secs = (moments[-1]["secs"] - moments[0]["secs"]) if len(moments) > 1 else 0
    states = build_states(moments)
    apps = []
    for s in states:
        if s.name not in apps and not s.name.startswith(("The screen", "The rest of the screen", "A window", "Loose words")):
            apps.append(s.name)
    clocks = [c for m in moments for p in m.get("panes") or [] for c in [old.clock_in(p)] if c]
    parts = [f"# {title}", ""]
    head = f"A screen recording, {old.minutes(secs)} read, {len(moments)} screen moments, {len(states)} window states."
    if apps:
        head += " On screen: " + "; ".join(apps) + "."
    if clocks:
        head += f" The desktop clock read {clocks[0]}" + (f" at the start and {clocks[-1]} at the end." if clocks[-1] != clocks[0] else ".")
    parts += [head, "", "**The order of events**", ""]
    for s in states:
        what = f", {s.title}" if s.title else ""
        span = s.times[0] if len(s.times) == 1 else f"{s.times[0]} to {s.times[-1]}"
        parts.append(f"- {span} - {s.name}{what}")
    parts += ["", "---", ""]
    by_name = {}
    for s in states:
        by_name.setdefault(s.name, []).append(s)
    for s in states:
        parts.append(s.heading())
        parts.append("")
        w = s.window_html()
        if w:
            parts.append(w)
            parts.append("")
        for ln in s.said_html():
            parts.append(ln)
            parts.append("")
        f = s.fine_html()
        if f:
            parts.append(f)
            parts.append("")
        others = [o for o in by_name[s.name] if o is not s]
        if others:
            parts.append("Other states of this same window: " + " · ".join(
                f"{o.times[0]} {o.title or 'as drawn there'}" for o in others))
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
