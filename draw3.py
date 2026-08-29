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
import math
import difflib
import html
import os
import re
import struct
import sys

import machine
import draw as old          # HTML line helpers that do not change
import draw2                 # the geometry: items, tables rebuilt, window groups
import shapes                # where each window sat, measured off the frame
import panes                 # which of the frame's rectangles are panes, not windows

LONG_SAID = 700
MAX_DOUBT = 12
STITCH_MIN = 0.8            # a row or line is "the same" at this ratio


def esc(s):
    return html.escape(str(s), quote=False)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


MAX_NAMES = 6


def junky(s):
    """A reading with no word in it: letters the engines guessed at.

    Word-likeness decides this, never length. A folder really can be called
    Dev, or src, or bin, and throwing away every reading under four letters
    threw those away with the letter-soup - "Dev" went missing out of a tree
    it plainly sat in. What marks a guess is a run of letters that no word
    could be: no vowel in it at all."""
    toks = re.findall(r"[A-Za-z][A-Za-z'\u2019_.]*", s)
    if not toks:
        return True
    good = sum(1 for t in toks if re.search(r"[aeiouyAEIOUY]", t) and len(t) >= 3)
    return good * 2 < len(toks) or len(re.sub(r"[^A-Za-z0-9]", "", s)) < 2


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


def same_title(a, b):
    """Two readings of a window's title are the same title when they read
    the same, or one is the other cut short by Finder's own ellipsis.

    `same_text` was used here and it holds a substring match for anything
    over eight letters - so `jaredrhodenizer` matched
    `-Users-jaredrhodenizer-Documents-jarvis...` and the folder opened at
    00:01:00 was filed as a moment of the folder before it, its two rows
    drawn under the wrong name and its own card never written. A title is a
    whole name; a name inside another name is a different folder."""
    if not a or not b:
        return False
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    for cut, full in ((a, b), (b, a)):
        c = cut.strip()
        if c.endswith(("...", "\u2026")):
            head = norm(c.rstrip(".\u2026"))
            if len(head) >= 8 and norm(full).startswith(head):
                return True
    # the same name with at most two letters read differently - and never a
    # name found INSIDE another, which is what `same_name` allows through
    return (len(na) >= 6 and len(na) == len(nb) and len(na) <= 24
            and sum(1 for x, y in zip(na, nb) if x != y) <= 2)


def bare_dot(nm):
    """A name without the reader's own full stop on its end: `memory.` is
    `memory`. No name ends in a bare stop, and a file's stop has letters
    after it."""
    nm = str(nm or "")
    if len(nm) > 2 and nm.endswith(".") and not nm.endswith("..") and "." not in nm[:-1].lstrip("."):
        return nm[:-1]
    return nm


# Finder's kinds are a fixed vocabulary; a reading that matches one letter
# for letter, spaces aside, is that kind spelt as Finder spells it
KIND_CANON = ["Folder", "Document", "JSON", "Log File", "Markdo...text file", "Markdown text file",
              "Application", "PNG image", "JPEG image", "Plain Text", "Text Document", "Alias",
              "Unix executable", "Zip archive", "Python script", "JavaScript", "Shell script"]
_KIND_KEY = {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in KIND_CANON}


def canon_kind(text):
    key = re.sub(r"[^a-z0-9]", "", str(text or "").lower())
    return _KIND_KEY.get(key, text)


def fold_twins(table, sni=0):
    """One row read twice under two spellings of its name is one row: the
    same date, size and kind cell for cell, and names alike (`clauds son`
    beside `.claude.json`, `user_review.qdrafts_...` beside
    `user_review_drafts_...`). The better-confirmed name stands and the
    band goes with it."""
    rows = table.rows
    hdr = getattr(table, "header", None) or []
    if not (sni < len(hdr) and hdr[sni] and "Name" in hdr[sni]):
        return                      # a Size or Kind column is never a name
    out = []
    for r in rows:
        nm = r["cells"][sni] if sni < len(r["cells"]) else ""
        rest = [c for i, c in enumerate(r["cells"]) if i != sni]
        if not nm or sum(1 for c in rest if c) < 2 or GLUED_SIZE.search(nm) or GLUED_DATE.search(nm):
            out.append(r)
            continue
        twin = None
        for o in out:
            om = o["cells"][sni] if sni < len(o["cells"]) else ""
            orest = [c for i, c in enumerate(o["cells"]) if i != sni]
            if not om or len(orest) != len(rest):
                continue
            if not all(norm(a) == norm(b) for a, b in zip(rest, orest) if a and b) or not any(a and b for a, b in zip(rest, orest)):
                continue
            x, y = norm(nm), norm(om)
            alike = (x == y or (min(len(x), len(y)) >= 5 and abs(len(x) - len(y)) <= 2
                     and difflib.SequenceMatcher(None, x, y, autojunk=False).ratio() >= 0.75))
            if alike:
                twin = o
                break
        if twin is None:
            out.append(r)
            continue
        # the name read most often stands (`.claude.json` at three moments
        # over `clauds son` at one), then the confirmed one, then the fullest
        def _weight(row_, name_):
            v_ = row_.get("_names") or {}
            sure_ = not (row_.get("italic") and row_["italic"][sni])
            return (sum(v_.values()) if v_ else (2 if sure_ else 1), sure_,
                    sum(1 for ch in name_ if not ch.isalnum()), len(name_))
        if _weight(r, nm) > _weight(twin, twin["cells"][sni]):
            twin["cells"][sni] = nm
            twin["italic"][sni] = False
            twin["_names"] = dict(r.get("_names") or {})
        for i, c in enumerate(r["cells"]):
            if i < len(twin["cells"]) and c and not twin["cells"][i]:
                twin["cells"][i] = c
        if r.get("band") and not twin.get("band"):
            twin["band"] = r["band"]
    table.rows = out


def same_name(a, b):
    """Two readings of one file name: the same after norm, or the same
    length with at most two letters read differently (0olnbox / ooInbox),
    or a letter dropped or added. NEVER one name inside another:
    `.claude.json` sits inside `.claude.json.backup`, and `same_text`'s
    containment rule stitched the two files into one row, whose votes
    then renamed the first for the second."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) == len(b) and len(a) <= 12 and sum(1 for x, y in zip(a, b) if x != y) <= 2:
        return True
    return (min(len(a), len(b)) >= 6 and abs(len(a) - len(b)) <= 1
            and difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.9)


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
        # ONE LIST OF (MOMENT, READING), NOT TWO LISTS SIDE BY SIDE. It was
        # `paths` and `path_at` kept in step by hand, and they came apart: one
        # table copied `paths` from another without its moments, so the `zip`
        # pairing them silently kept NOTHING -- two readings lost their moments,
        # no error and no trace. Measured, one table of forty-seven. A pair
        # cannot come apart.
        self.readings = []      # (moment, path bar read), latest last
        self.now = None         # the moment being read; a cursor, not a store
        self.rh = 0.0           # a row's height in frame pixels
        self.spoiled = 0        # lines dropped: two columns misread at once
        self.bottom = []
        self.banded_names = set()

    @property
    def paths(self):
        """Every path bar read, latest last -- read-only, because a list of
        readings without the moments they were read at is the fault above."""
        return [p for _, p in self.readings]

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
        # A SENTENCE IS NOT A COLUMN HEADING. Finder's tooltip "See folders
        # you viewed previously" hung over the Name heading at 00:03:40 and
        # was read as the heading; a heading is one or two words.
        if head and sum(1 for h in head if h in FINDER_WORDS) >= 1:
            head = [("Name" if (i == 0 and "Name" not in head) else "") if (h and h not in FINDER_WORDS and h.count(" ") >= 2) else h
                    for i, h in enumerate(head)]
        # A heading holding SEVERAL of Finder's headings means the reader ran
        # the columns together, and the cells under it are glued too. Where
        # the cells plainly hold a date or a size, the column is cut back
        # apart rather than named for one of them and left glued.
        wide_ = []
        for i, h in enumerate(head):
            parts_ = draw2.split_heads(h)
            if len(parts_) < 2:
                continue
            col = [cells_[i] for cells_, _, _ in rows if i < len(cells_) and cells_[i]]
            if col and sum(1 for c in col if GLUED_DATE.search(c) or GLUED_SIZE.search(c)) * 2 >= len(col):
                wide_.append((i, parts_))
        if wide_:
            head2, rows2 = [], [[] for _ in rows]
            for i, h in enumerate(head):
                cut = next((q for j, q in wide_ if j == i), None)
                head2.extend(cut if cut else [h])
                for k, (cells_, _, _) in enumerate(rows):
                    c = cells_[i] if i < len(cells_) else ""
                    rows2[k].extend(cut_glued(c, cut) if cut else [c])
            head = head2
            rows = [(rows2[k], icon_, band_)
                    for k, (_c, icon_, band_) in enumerate(rows)]
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
        # A LONE CRUMB IS THE PATH BAR, NOT A FILE. Read on a window the
        # screen cut off, the bar's one visible crumb (`er-Documents-jarvis-demo >`)
        # came back as a row of the list and was drawn with a folder icon
        # between two files' sizes.
        rows = [(cells, icon, band) for cells, icon, band in rows
                if not (cells and cells[0] and str(cells[0]).rstrip().endswith((">", "\u203a"))
                        and not any(cells[1:]))]
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
        # A DATE GLUED TO THE END OF A NAME IS THE DATE COLUMN, NOT THE NAME.
        # Read as one cell, `feedback_lo...kimmers.md Jun30,2026at5:51PM`
        # matched `feedback_id.andlers.md Jun 30, 2026 at 5:51PM` as the same
        # row - the shared date made two different files alike enough - and
        # the list came out with three rows named for one file. The date is
        # cut off the name here, before any row is matched by its name.
        di_ = next((k for k, g in enumerate(self.header) if g and "Date Modified" in g), None)
        for r_ in new_rows:
            nm_ = r_["cells"][0] if r_["cells"] else ""
            m_ = GLUED_DATE.search(nm_) if nm_ else None
            if not m_ or m_.end() < len(nm_.rstrip()) - 1:
                continue
            # A NAME THAT IS ONLY A DATE IS A DATE WITH THE NAME MISSED: the
            # row keeps its size and kind and its name stays blank, which is
            # what was read. `Jun30,2026at5:51PM` stood as a file's name in
            # the memory list.
            r_["cells"][0] = nm_[:m_.start()].strip()
            date_ = tidy_date(m_.group(1).strip()) or m_.group(1).strip()
            if di_ is None:
                at_ = 1
                self.header.insert(at_, "Date Modified")
                for q_ in self.rows:
                    q_["cells"].insert(at_, "")
                    q_["italic"].insert(at_, False)
                for q_ in new_rows:
                    q_["cells"].insert(at_, "")
                    q_["italic"].insert(at_, False)
                di_ = at_
            if di_ < len(r_["cells"]) and not r_["cells"][di_]:
                r_["cells"][di_] = date_
                r_["italic"][di_] = False
        def keep(o, n):
            # EVERY READING OF THE NAME IS COUNTED, and the spelling most
            # readings agree on wins at `tidy`. Taking the first confirmed
            # reading left `.Jocal` standing over two later readings of
            # `.local`, because the wrong one happened to be read first and
            # confirmed by both engines that once.
            votes = dict(o.get("_names") or {})
            if o["cells"] and o["cells"][0] and not votes:
                votes[bare_dot(o["cells"][0])] = votes.get(bare_dot(o["cells"][0]), 0) + (2 if not (o["italic"] and o["italic"][0]) else 1)
            if n["cells"] and n["cells"][0]:
                votes[bare_dot(n["cells"][0])] = votes.get(bare_dot(n["cells"][0]), 0) + (2 if not (n["italic"] and n["italic"][0]) else 1)
            # twins: the confirmed reading stands over the doubtful one,
            # and a cell the old row lacks is filled from the new
            if o["italic"] and o["italic"][0] and n["cells"] and n["cells"][0] and not (n["italic"] and n["italic"][0]):
                o = {"cells": [n["cells"][0]] + o["cells"][1:], "italic": [False] + o["italic"][1:], "band": o["band"] or n["band"], "icon": o.get("icon") or n.get("icon")}
            o["_names"] = votes
            cells = list(o["cells"])
            italics = list(o["italic"])
            for i, c in enumerate(n["cells"]):
                if i < len(cells) and not cells[i] and c:
                    cells[i] = c
                    italics[i] = n["italic"][i] if i < len(n["italic"]) else False
            # THE BAND IS THE LATEST MOMENT'S. A selection is a property of
            # the moment, and a row read again at a later moment carries
            # that moment's band or none: kept sticky, `03 Company B` stood
            # green on a card spanning eight moments because it was selected
            # at one of them.
            return {"cells": cells, "italic": italics, "band": n["band"], "icon": o.get("icon") or n.get("icon"),
                    "_names": votes}
        self.rows = stitch(self.rows, new_rows, key=lambda r: r["cells"][0] if r["cells"] else "", same=same_name, merge=keep)
        for r in self.rows:
            votes = r.get("_names") or {}
            if len(votes) > 1 and r["cells"] and r["cells"][0]:
                # a spelling read with its dot or its capital intact ranks
                # above a barer one on a tie
                # ONE WORD, HOWEVER SPELT, IS ONE VOTE: `Brand Guide.md` and
                # `BrandGuide.md` are the same name read with and without
                # its space, and pooled they outvote a misreading; among the
                # spellings of the winning word the fullest stands (spaces,
                # capitals, punctuation survive OCR worst).
                groups_ = {}
                for nm_, v_ in votes.items():
                    groups_.setdefault(norm(nm_), []).append((nm_, v_))
                gk = max(groups_, key=lambda k: sum(v for _, v in groups_[k]))
                best = max((nm_ for nm_, _ in groups_[gk]),
                           key=lambda nm: (sum(1 for ch in nm if not ch.isalnum()), sum(ch.isupper() for ch in nm), len(nm)))
                cur_ = r["cells"][0]
                if best != cur_ and (norm(cur_) == gk or sum(v for _, v in groups_[gk]) > sum(v for _, v in groups_.get(norm(cur_), []))):
                    r["cells"][0] = best
                    if r["italic"]:
                        r["italic"][0] = False
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
            # THE SAME OTHER CELLS, LETTER FOR LETTER. Judged by likeness, a
            # row of `Jun 30 ... 60 bytes Markdown` folded into the row of
            # `Jun 30 ... 59 bytes Markdown` beside it, and a file the
            # screen showed was gone from the list.
            def _twin_of(n_):
                # every cell the nameless row HAS must match; a cell it
                # lacks was not read, which is no difference
                if len(n_["cells"]) < len(r["cells"]):
                    return False
                return all(not c or norm(c) == norm(n_["cells"][i])
                           for i, c in enumerate(r["cells"]) if i >= 1)
            twin = next((n for n in named if rest and _twin_of(n)), None)
            if twin is None and rest and len(named) < 2:
                kept.append(r)
            elif twin is None and sum(1 for c in r["cells"][1:] if c) >= 2 and len(named) >= 2:
                # A ROW WITH ITS DATE, SIZE AND KIND READ AND ITS NAME MISSED
                # IS A ROW OF THE LIST, not the window behind: Finder gives
                # every row a name, and this one's was not read. It stands
                # with its name blank rather than being thrown away.
                kept.append(r)
        self.rows = kept
        fold_twins(self, 0)
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
        # a whole path bar read as ONE word keeps its chevrons inside it:
        # cut after each one, and the crumbs come back separate, each still
        # carrying the chevron that proves it was a crumb
        def _cut_crumbs(row):
            out = []
            for it in row:
                parts = [q.strip() for q in re.split(r"(?<=[>\u203a])", it["text"])
                         if q.strip()]
                # only a reading that swallowed a WHOLE bar is cut up: it
                # starts at the disk and holds at least two chevrons. A lone
                # crumb standing beside other words is left as it was read.
                if len(parts) >= 3 and norm(parts[0].rstrip(">\u203a")) in (
                        norm("Macintosh HD"), norm("MacintoshHD")):
                    out.extend(dict(it, text=q) for q in parts)
                else:
                    out.append(it)
            return out
        rows_below = [_cut_crumbs(r) for r in rows_below]
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
        best = unglue(best)
        if len(best) >= len(self.path):
            self.path = best
        if best and best not in self.paths:
            self.readings.append((self.now, best))
        self.tidy()

    def tidy(self):
        """Cells put back the way Finder drew them: dates in Finder's date
        shape (a date that parses is its own confirmation), a size leading a
        Kind cell split out into the Size column -- the column added when the
        reader missed its heading."""
        hdr = self.header
        for r in self.rows:
            nm = r["cells"][0] if r["cells"] else ""
            # the reader's own full stop on a folder's name (`memory.`): no
            # name ends in a bare stop, and a file's stop has letters after it
            r["cells"][0] = bare_dot(nm)
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
            for r in self.rows:
                if ki < len(r["cells"]) and r["cells"][ki]:
                    r["cells"][ki] = canon_kind(r["cells"][ki])
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
        self.blocks = []        # (pane top, pane foot, [texts]) - where each pane's lines SAT

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
            t = t.strip().strip("#*>│ ˃˅").strip()
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


def bar_crumbs(pane):
    """A window's path bar cut as a pane of its own: the disk, then the
    folders down to what the window shows.

    The bar sits at the foot of every Finder window, and where the window's
    foot falls outside the rectangle the frame measured, the reader files it
    as a pane of loose words. Read that way its crumbs become stray words of
    the list, and the window loses the one thing that says which folder it
    is showing. The chevrons between the crumbs are what marks it a bar,
    whether the reading kept them in one word or several."""
    parts = []
    for it in draw2.items_of(pane):
        t = str(it.get("text") or "")
        bits = [q.strip() for q in re.split(r"[>\u203a]", t) if q.strip()]
        if len(bits) >= 2:
            parts.extend(bits)
        elif parts:
            break
    if len(parts) >= 3:
        if norm(parts[0]) == norm("Macintosh HD"):
            return parts
        # THE READER DROPS A CHEVRON AND GLUES THE DISK TO THE FOLDER AFTER
        # IT. At 00:01:00 the bar came back as `Macintosh HD Users
        # >jaredrhodenize>.claude projects>-Users-...-jarvis-dem`, so the
        # first piece was `Macintosh HD Users`, this refused the whole bar,
        # and the window lost its path - and with no path, no name, so it was
        # titled `jaredrhodenizer` where the frame reads the long one. The
        # disk's own name still says plainly where the bar begins, so it is
        # cut off the front rather than the bar being thrown away. Only the
        # disk is split off: a space inside any OTHER crumb may belong to the
        # folder's name, and guessing there would invent a crumb.
        head = re.match(r"\s*(Macintosh\s*HD)\b[\s\u203a>]*(.*)$", parts[0], re.I)
        if head:
            rest = head.group(2).strip()
            return [head.group(1)] + ([rest] if rest else []) + parts[1:]
    return []


def bar_across(group, m):
    """A path bar the reader cut into several panes, read back as one.

    `bar_crumbs` asks ONE pane for the whole bar. At 00:00:50 the strip under
    a Finder came back as four panes with the bar's own words cut across them
    - `Maci` | `ntoshHD>` | `Users` | `jaredrhode` | `nizer>` - so no pane
    held even two crumbs and the window got no path, and with no path no
    name. The words of one ROW, read left to right and run together, are that
    row's bar; a chevron the reader dropped only glues two crumbs into one
    rather than losing them.

    LEFT TO RIGHT AND NEVER BACKWARDS. Gathered from every pane at that
    height, two panes' worth of the same bar ran together and the crumbs came
    out doubled. A word beginning left of where the last one ended is a
    second reading of ground already covered, not the next crumb along.
    """
    H = (m.get("size") or [1920, 1080])[1]
    its = [it for p in group.get("panes") or [] for it in draw2.items_of(p)
           if str(it.get("text") or "").strip()]
    best = []
    for seed in its:
        row = sorted((it["box"][0], it["box"][2], str(it["text"]))
                     for it in its
                     if abs(it["box"][1] - seed["box"][1]) <= 0.01 * H)
        kept, reach = [], None
        # THE GAP BETWEEN TWO CRUMBS IS A CHEVRON THE READER DID NOT KEEP.
        # Finder sets `› [icon]` between crumbs, and the engines read the
        # words and drop the marks; run together, `02 Company A (Info
        # Product)` and `Dev` became one crumb and the bar lost its last
        # folder. Two words a whole letter-height apart on one row were
        # never one crumb: a space inside a folder's name is a fraction of
        # that.
        hs = sorted(it["box"][3] - it["box"][1] for it in its
                    if abs(it["box"][1] - seed["box"][1]) <= 0.01 * H)
        h_ = hs[len(hs) // 2] if hs else 0
        for x0, x1, txt in row:
            if reach is not None and x0 < reach - 8:
                continue
            if reach is not None and h_ and x0 - reach > 1.0 * h_ and not re.search(r"[>\u203a]\s*$", kept[-1] if kept else ""):
                kept.append("\u203a")
            kept.append(txt)
            reach = x1
        parts = [q.strip() for q in re.split(r"[>\u203a]", "".join(kept)) if q.strip()]
        # A PATH NEVER PASSES THROUGH THE SAME FOLDER TWICE. Where the row
        # holds the bar read over again - a second pane covering ground the
        # first already had, at a height the no-overlap rule could not tell
        # apart - the crumbs come back doubled, and the drawn bar read
        # `... > .claude > projects > Usersjaredrhodenizer > ... > .claude`.
        # It ends at the first crumb it has already seen.
        seen_, cut_ = set(), []
        for c in parts:
            n_ = norm(c)
            if n_ in seen_:
                break
            seen_.add(n_)
            cut_.append(c)
        parts = cut_
        if len(parts) >= 3 and norm(parts[0]) == norm("Macintosh HD") \
                and len(parts) > len(best):
            best = parts
    return best


GLUED_DATE = re.compile(
    r"[a-z0-9]?((?:Today|Yesterday|[A-Z][a-z]{2}\s?\d{1,2},?\s?\d{4})"
    r"\s?(?:at)?\s?\d{1,2}:\d{2}\s?[AaPp]\.?[Mm])")
GLUED_SIZE = re.compile(r"(\d+(?:[.,]\d+)?\s?(?:bytes|byte|KB|MB|GB|TB))", re.I)


def cut_glued(cell, parts_):
    """One cell holding several columns' text, cut back into them.

    The reader sometimes runs a list's headings together - "Name Date
    Modified Size" as one heading - and then every cell under it holds the
    name, the date and the size in one string. Left glued, the file's NAME
    carries a date on the end of it, and a name with a date stuck to it
    matches the wrong row in every pass that works by name afterwards.
    The date and the size say plainly where they begin, so the cell is cut
    at them and each piece goes to its own column."""
    out = {q: "" for q in parts_}
    rest = cell
    name_ = rest
    m = GLUED_DATE.search(rest)
    if m and "Date Modified" in parts_:
        out["Date Modified"] = m.group(1).strip()
        name_ = rest[:m.start()].strip()
        rest = rest[m.end():].strip()
    else:
        rest = ""
    m2 = GLUED_SIZE.search(rest)
    if m2 and "Size" in parts_:
        out["Size"] = m2.group(1).strip()
        rest = (rest[:m2.start()] + " " + rest[m2.end():]).strip()
    if rest and "Kind" in parts_:
        out["Kind"] = rest
    elif rest:
        name_ = (name_ + " " + rest).strip()
    # `parts_[0]` is the NAME column only when the glued heading BEGINS with
    # the name. Where the reader ran `Date Modified` and `Size` together with
    # no name in front of them, `parts_[0]` IS `Date Modified`, and this line
    # then overwrote the date it had just cut out of the cell with whatever
    # stood before it - nothing. Every row of three pictures lost its date to
    # that one assignment, and only rows the same window drew again at another
    # moment, through a cleanly-read heading, kept theirs.
    if not out.get(parts_[0]):
        out[parts_[0]] = name_
    return [out[q] for q in parts_]


MARKER = re.compile(r"^(\s*(?:[-*\u2022#>]+\s*)*)")


def _hole(short, long_):
    """The words left where a cover cut the line: what survived must be the
    START of the first word put back, or the END of the last. "it" for "its
    own folder and the daily log. It", "s" for "something outside its lane".
    Without this a bullet is merged with the bullet beside it, and the note
    is made to say a sentence it never said."""
    if not short or not long_:
        return False
    def k(w):
        return re.sub(r"[^a-z0-9]", "", w.lower())
    a, b = k(short[0]), k(long_[0])
    # a STRICT extension: a word that is simply the same word says nothing
    # about a hole, and "the" facing "the" would let any two lines merge
    if a and b and b != a and b.startswith(a):
        return True
    a2, b2 = k(short[-1]), k(long_[-1])
    return bool(a2 and b2 and b2 != a2 and b2.endswith(a2))


def mend_prose(states):
    """A line of a note that something covered, filled from a reading of the
    SAME line taken when nothing did.

    The camera sits over one corner of every frame, so a line of the note
    running under it is read short - "it only knows it" where the note said
    "it only knows its own folder and the daily log. It". The same note,
    read at a moment when it stood behind the other windows, was read whole
    in the gaps between them.

    The two readings are merged the only way that invents nothing: every
    word of the result comes from one reading or the other. Where they
    agree, the words stand; where one has words the other lacks between two
    places they agree, those words go in; where a hole in one faces a run
    in the other, the run fills the hole. A line is only merged with a line
    it plainly IS - five words in common at least - and never grows by more
    than half again, so a reading of some other line cannot walk in.
    """
    docs = [q["model"] for st in states for q in st.parts
            if q["fam"] == "doc" and getattr(q["model"], "lines", None)]

    def bare(w):
        # the note's own emphasis marks are not part of the word, and a
        # word put back with them still on would show its asterisks
        return re.sub(r"^[*_]+|[*_]+$", "", w)

    def key(w):
        return re.sub(r"[^a-z0-9]", "", w.lower())

    pool = []
    for d in docs:
        for t, _h in d.lines:
            ws = [bare(w) for w in MARKER.sub("", t).split()]
            if len(ws) >= 6:
                pool.append((d, ws, [key(w) for w in ws]))

    def merge_line(mine, mine_l, other, other_l):
        """The two readings as one, or None where they are not the same line."""
        sm = difflib.SequenceMatcher(None, mine_l, other_l, autojunk=False)
        ops = sm.get_opcodes()
        equal = sum(i2 - i1 for tag, i1, i2, _j1, _j2 in ops if tag == "equal")
        if equal < 5 or equal < 0.55 * min(len(mine), len(other)):
            return None
        # TWO READINGS OF THE SAME LINE NEVER CONTRADICT EACH OTHER. They
        # differ only by what one of them lost: a hole where something
        # covered the words. So a place where the two say DIFFERENT words
        # is proof that these are different lines - two bullets of one note
        # share their shape and half their words, and merging those would
        # make the note say a sentence it never said. The only kind of
        # disagreement allowed is a cut word: what survived must be the
        # start of the first word put back, or the end of the last.
        out, seen_equal, filled = [], False, False
        for tag, i1, i2, j1, j2 in ops:
            if tag == "equal":
                out.extend(mine[i1:i2])
                seen_equal = True
            elif tag == "delete":
                out.extend(mine[i1:i2])
            elif tag == "insert":
                if not seen_equal:
                    return None       # its head, not ours: a different line
                out.extend(other[j1:j2])
                filled = True
            else:
                run, cut = other[j1:j2], mine[i1:i2]
                if seen_equal and len(cut) <= 2 and len(run) > len(cut) \
                        and _hole(cut, run):
                    out.extend(run)
                    filled = True
                elif seen_equal and len(cut) <= 5 and _hole(cut[:1], run) \
                        and [key(w) for w in cut[1:]] != [key(w) for w in run[-(len(cut) - 1):]]:
                    # the cut word, then words of ours that simply run on
                    # past where the other reading stopped
                    out.extend(run)
                    out.extend(cut[1:])
                    filled = True
                else:
                    return None       # they contradict: not the same line
        if not filled or out == mine or len(out) > 1.5 * len(mine):
            return None
        return out

    for d in docs:
        for i, (t, h) in enumerate(list(d.lines)):
            lead = MARKER.match(t).group(1)
            core = t[len(lead):]
            mine = [bare(w) for w in core.split()]
            if len(mine) < 6:
                continue
            grew = True
            while grew:
                grew = False
                mine_l = [key(w) for w in mine]
                for od, ow, ow_l in pool:
                    if od is d:
                        continue
                    got = merge_line(mine, mine_l, ow, ow_l)
                    if got:
                        mine, mine_l, grew = got, [key(w) for w in got], True
                        break
            new_core = " ".join(mine)
            if new_core == core:
                continue
            if esc(core) in h:
                new_h = h.replace(esc(core), esc(new_core), 1)
            elif core in h:
                new_h = h.replace(core, esc(new_core), 1)
            else:
                continue          # formatting in the way: leave it be
            d.lines[i] = (lead + new_core, new_h)


def flatten_sidebars(states):
    """A Finder window's sidebar drawn FLAT, the way it stands.

    Read on its own - the window's list hidden behind whatever is in front -
    the fixed list down the left of every Finder window comes back with the
    shape of a tree, and drawn as one it grows guide lines and open-or-shut
    marks: "Applications" hanging off "Shared", which is nesting that was
    never on the screen. The names are kept exactly as read; only the marks
    that claim a structure are taken off."""
    side = {norm(n) for n in draw2.SIDE_NAMES}
    for st in states:
        for q in st.parts:
            if q["fam"] != "tree" or not getattr(q["model"], "lines", None):
                continue
            names = [row_name(t) for t, _h in q["model"].lines]
            named = [n for n in names if n]
            if len(named) < 4:
                continue
            if sum(1 for n in named if norm(n) in side) < 0.6 * len(named):
                continue
            fixed = []
            for t, h in q["model"].lines:
                n = row_name(t)
                lead = t[:len(t) - len(t.lstrip("\u2502 \u02c3\u02c5"))]
                if lead:
                    h = h.replace(esc(lead), "", 1) if esc(lead) in h else h
                fixed.append((n, h))
            q["model"].lines = fixed


def tidy_side(table, house=None, title=None):
    """A sidebar holds the fixed favorites and the home folder, nothing
    else: a crumb of the path bar glued into one word and filed as a
    sidebar name (`Usersjaredrhodeniz`) is not a favorite, and an icon's
    scrap in front of a name (`(] Desktop`) is not part of it."""
    import draw2 as _d2
    if not table or not getattr(table, "side", None):
        return
    canon = {norm(n): n for n in _d2.SIDEBAR_WORDS}
    for h in (house or []):
        canon.setdefault(norm(h), h)
    crumbs = {norm(c) for c in (getattr(table, "path", None) or [])}
    out = []
    for w in table.side:
        bare_ = re.sub(r"^[^A-Za-z]+", "", str(w)).strip()
        key = norm(bare_)
        hit = canon.get(key) or next((c for k, c in canon.items()
                                      if len(k) >= 5 and key.endswith(k) and len(key) - len(k) <= 3), None)
        if not hit and key and (key in crumbs or (title and key == norm(title))) and " " not in bare_:
            hit = bare_               # the home folder, named after the user
        if hit and hit not in out:
            out.append(hit)
    if len(out) >= 3:
        table.side = out


def sidebar_from_panes(st, house=None):
    """A Finder window's favorites sidebar, read by the reader as a document
    or a tree standing left of the list, put back as the window's sidebar.

    At 00:00:00 the left Finder's sidebar came back as an open document -
    `EC): Recents`, `fH: Movies`, `(] Desktop`, `@® Downloads` - with the
    rest of its names as loose words on the same pane, and the window was
    drawn with no sidebar at all while the frame shows one. The names are
    the fixed macOS favorites, and a column of them standing hard against
    the list's left edge is the sidebar, whatever the reader filed it as.
    Only names actually read on the pane are drawn; the order is the house
    order (the fullest sidebar read anywhere in the video), since the
    favorites stand in one order in every window."""
    import draw2 as _d2
    t = st.main_table()
    if st.name != "The Finder window" or t is None or getattr(t, "side", None):
        return False
    tp = next((q for q in st.parts if q["fam"] == "table" and q["model"] is t), None)
    if not tp or tp.get("x0") is None:
        return False
    canon = {norm(n): n for n in _d2.SIDEBAR_WORDS}
    for h in (house or []):
        canon.setdefault(norm(h), h)

    def _name(txt):
        w = re.sub(r"^[^A-Za-z]+", "", str(txt)).strip()
        key = norm(w)
        if not key:
            return None
        if key in canon:
            return canon[key]
        # icon garbage glued to the front of the name: the name is its tail
        return next((c for k, c in canon.items()
                     if len(k) >= 5 and key.endswith(k) and len(key) - len(k) <= 3), None)

    found, used = {}, []
    share_seen = []
    for m, g in getattr(st, "pieces", ()):
        panes_ = g.get("panes") or []
        # THE LIST PANE OF THIS SAME MOMENT SETS THE LIMIT. A part's x-span
        # is gathered across moments at different zooms, so it cannot say
        # where the list stood on any one frame; the list pane cut from this
        # frame can.
        lists_ = [p_ for p_ in panes_ if p_.get("kind") == "a list of columns"]
        if not lists_:
            continue
        lx0 = min(p_["box"][0] for p_ in lists_)
        lx1 = max(p_["box"][2] for p_ in lists_)
        lim = lx0 + 0.1 * max(1.0, lx1 - lx0)
        for p in panes_:
            if p.get("kind") == "a list of columns":
                continue
            b = p.get("box")
            if not b or b[2] > lim or b[0] >= lx0:
                continue
            texts = [(it["text"], it["box"][1]) for it in _d2.items_of(p)]
            for ln in p.get("lines") or []:
                q_ = ln.strip()
                if q_.startswith("[also on this pane"):
                    for w in q_.split("]", 1)[1].split("|"):
                        texts.append((w.strip(), None))
                elif q_ and not q_.startswith(("[", "---", "unsettled")):
                    texts.append((re.split(r"\s+<- ", q_)[0].strip(), None))
            got = 0
            for txt, y in texts:
                c = _name(txt)
                if c:
                    got += 1
                    if c not in found or (found[c] is None and y is not None):
                        found[c] = y
            if got >= 3:
                used.append(p)
                r_ = g.get("rect")
                if r_ and r_[2] > r_[0]:
                    share_seen.append((b[2] - r_[0]) / float(r_[2] - r_[0]))
    if len(found) < 4:
        return False
    order = list(house) if house else sorted(found, key=lambda c: (found[c] is None, found[c] or 0))
    side = [c for c in order if c in found] + [c for c in found if c not in order]
    t.side = side
    # the parts the reader built from those panes were the sidebar, not a
    # note or a tree standing in the window: they go, so the window is not
    # drawn with a document column beside its list
    for p in used:
        b = p["box"]
        for q in list(st.parts):
            if q["fam"] in ("doc", "tree", "words") and q.get("x0") is not None \
                    and q["x0"] >= b[0] - 4 and (q["x1"] or 0) <= b[2] + 4:
                st.parts.remove(q)
    # how wide the sidebar stood, measured off the pane the reader cut,
    # against the window's own rectangle on that same frame
    shares = [v for v in share_seen if 0.12 <= v <= 0.45]
    if shares:
        st.side_shares = sorted(set(shares) | set(getattr(st, "side_shares", None) or []))   # the card takes the widest window's
    if shares and not getattr(st, "side_share", None):
        st.side_share = sorted(shares)[len(shares) // 2]
    return True


def folder_marks(table):
    """The crumbs that name the folder, the generic ones left out."""
    return {norm(c) for c in table.path if norm(c) not in GENERIC and len(norm(c)) >= 3}


class Seen:
    """One window AS IT STOOD AT ONE MOMENT -- the observation, kept apart
    from the identity that runs through the moments.

    Multiple-object tracking draws exactly this line and its whole discipline
    rests on it: a DETECTION is what one frame showed, a TRACK is the identity
    carried across frames. `State` is the track. This is the detection, and it
    is the ONLY home of anything measured off a single frame.

    WHY IT EXISTS. `State` spans time, and every per-moment fact was hung off
    it in a side-table keyed by timestamp -- `rects`, `measured`, `_pitch_at`,
    `_doc_wide_at`, `_h1_read`, and `Table.path_at` beside them. SEVEN of them,
    one added each time a per-moment fact was caught being read at a moment it
    did not cover. That is a valid-time index hand-rolled one column at a time,
    and the faults it produced all rhymed: a title, a path, a selection, a
    pitch, a width, each taken from the wrong moment. One record per moment
    ends the class rather than its fifth instance."""
    __slots__ = ("ts", "rect", "measured", "pitch", "stood", "doc_wide", "h1", "pitch_cut")

    def __init__(self, ts):
        self.ts = ts
        self.rect = None        # where the window stood, worked out from what it drew
        self.measured = False   # the reader measured this window's own edges HERE
        self.pitch = None       # how far apart its rows really stood, here
        self.stood = None       # (where its words sat, the edges then, sure?)
        self.doc_wide = None    # how wide its note ran here, as a share of the pane
        self.h1 = None          # where its big heading sat here
        self.pitch_cut = False  # the pitch came off a list the screen cut, read loose

    def __repr__(self):
        return "Seen(%s%s)" % (self.ts, " measured" if self.measured else "")


class _AtView:
    """A read-only look at one field across the moments, so the old readers
    keep reading and nothing can WRITE a per-moment fact except through
    `State.at`. A plain dict here would let a write land on a throwaway copy
    and vanish silently, which is worse than the fault being replaced."""
    __slots__ = ("_seen", "_field")

    def __init__(self, seen, field):
        self._seen, self._field = seen, field

    def _pairs(self):
        for ts, sn in self._seen.items():
            v = getattr(sn, self._field)
            if v is not None and v is not False:
                yield ts, v

    def __getitem__(self, ts):
        for t, v in self._pairs():
            if t == ts:
                return v
        raise KeyError(ts)

    def get(self, ts, default=None):
        try:
            return self[ts]
        except KeyError:
            return default

    def __iter__(self):
        return (t for t, _ in self._pairs())

    def __contains__(self, ts):
        return any(t == ts for t, _ in self._pairs())

    def __len__(self):
        return sum(1 for _ in self._pairs())

    def __bool__(self):
        return any(True for _ in self._pairs())

    def keys(self):
        return [t for t, _ in self._pairs()]

    def values(self):
        return [v for _, v in self._pairs()]

    def items(self):
        return list(self._pairs())

    def __setitem__(self, ts, v):
        raise TypeError("a per-moment fact is written through State.at(ts, make=True), "
                        "never into a view -- see class Seen")


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
        self._now = None        # the moment being read right now, while absorbing
        self._seen = {}         # ts -> Seen: the ONE home of every per-moment fact,
                                # private, so no caller can hand one window's
                                # moments to another window or to a stretch
        # `_stood` was here: "where its words sat LAST, and the edges then" --
        # a per-moment fact with no moment on it, so "last" meant whichever
        # moment happened to run most recently against this object. It now
        # lives on the moment that saw it, and the moment before is asked for
        # by name.

    # ------------------------------------------------------ moment in, moment out

    _TS = re.compile(r"^\d\d:\d\d:\d\d$")

    def __setattr__(self, name, value):
        """REFUSE A NEW SIDE-TABLE. Folding the seven that existed into `Seen`
        fixes seven; it does nothing about the eighth, which is what actually
        happened here -- one was added every time a per-moment fact was caught
        being read at the wrong moment, and each was reasonable on the day.

        So the SHAPE is refused, not just its instances: an attribute named
        `..._at`, or any mapping whose keys are timestamps, may not be hung on
        a window. Both spellings the code actually used are caught. A dict
        assigned empty and filled later still slips through, which is stated
        here rather than left to be discovered -- the guard closes the idiom,
        not the language."""
        if name.endswith("_at") or (
                isinstance(value, (dict, set)) and value
                and all(isinstance(k, str) and State._TS.match(k) for k in value)):
            raise TypeError(
                "%r is a per-moment fact hung on a window that spans moments. "
                "Put it on Seen and reach it with State.at(ts) -- that is what "
                "the seven side-tables before it should have been." % name)
        object.__setattr__(self, name, value)

    def at(self, ts, make=False):
        """This window as it stood at ONE named moment, or None where this
        window was never seen at that moment.

        None means NOT SEEN HERE and it is not the same thing as "nothing was
        there" -- a caller that answers it with the window's span-wide value is
        borrowing another moment's fact, which is the whole class of fault this
        record exists to make visible. Reaching a per-moment fact without
        naming a moment is now impossible, which was the point."""
        got = self._seen.get(ts)
        if got is None and make:
            got = self._seen[ts] = Seen(ts)
        return got

    @property
    def rects(self):
        return _AtView(self._seen, "rect")

    @property
    def measured(self):
        return _AtView(self._seen, "measured")

    @property
    def _pitch_at(self):
        return _AtView(self._seen, "pitch")

    def moments(self):
        """Every moment this window was seen at, earliest first, with what was
        seen at each. The public way in, and the only one.

        It replaced two read-through properties that were reached as
        `getattr(st, "_h1_read", ())`. A default on a getattr swallows any
        AttributeError raised INSIDE a property and hands back an empty
        container -- so a broken record would have read as "nothing found",
        and "nothing found" is a legitimate answer everywhere in this file.
        That is a check whose failure is indistinguishable from its success,
        which is the shape that has cost this job the most. A method cannot be
        reached that way, and a break here is now loud."""
        return sorted(self._seen.items())

    def stood_before(self, ts):
        """Where this window's words sat at the LAST MOMENT BEFORE this one,
        or None if this is the first moment of it that was seen.

        Named, because the thing it replaced was not: a bare cache holding
        whichever moment ran most recently, which is not a fact about the
        window at all but about the order the code happened to walk."""
        earlier = [t for t, sn in self._seen.items() if t < ts and sn.stood]
        return self._seen[max(earlier)].stood if earlier else None

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
        # A READING WITH NO MOMENT ON IT CANNOT BE PLACED IN TIME AT ALL, and
        # that is worse than a reading placed at the wrong one. `absorb` stamps
        # the moment onto the parts a window ALREADY has, and then `_absorb`
        # creates the new ones through here and reads into them straight away
        # -- so the FIRST reading of every table was recorded blank. Measured
        # before this line: 23 readings of 38 carried no moment, and the rule
        # that picks the latest moment's reading skips every one of them.
        if hasattr(model, "now"):
            model.now = self._now
        part = {"fam": fam, "slot": slot, "model": model, "x0": None, "x1": None}
        self.parts.append(part)
        self.parts.sort(key=lambda q: q["slot"])
        return part

    def absorb(self, group, m):
        self._now = m["ts"]     # the moment being read; a cursor, not a store
        for q in self.parts:
            if hasattr(q["model"], "now"):
                q["model"].now = m["ts"]
        self._absorb(group, m)
        # the window's own path bar, where the reader cut it as a pane of
        # its own instead of as the foot of the list
        bar = []
        for p in group.get("panes") or []:
            c = bar_crumbs(p)
            if len(c) > len(bar):
                bar = c

        across = bar_across(group, m)
        if len(across) > len(bar):
            bar = across
        if bar:
            t_ = self.main_table()
            if t_ is not None and len(bar) > len(getattr(t_, "path", None) or []):
                t_.path = unglue(list(bar))
                if bar not in t_.paths:
                    t_.readings.append((m["ts"], list(bar)))
                # the name rule reads the path, and the path only just
                # arrived: ask it again now the window has its bar
                self._title_rule(again=True)
        # where the window stood at this moment, measured from what it drew
        self.at(m["ts"], make=True).rect = content_rect(self, group, m)
        if group.get("side_share"):
            self.side_share = group["side_share"]

    def _absorb(self, group, m):
        W = (m.get("size") or [1920])[0]
        rect = group["rect"]
        if not any(mm is m for mm, _ in self.pieces):
            self.pieces.append((m, group))
        # READING ORDER: down a column, then across to the next. Sorting by
        # x before y puts a pane a few pixels further right AFTER one below
        # it, which is right for two panes standing side by side and wrong
        # for two cut out of the same column -- measured, the note's own
        # heading and its Properties row were read at the top of the pane
        # and drawn at the BOTTOM of the note, because their slice sat a
        # little further right than the prose below them. The window's own
        # column bucket (`slot`, eighths of the screen) is what separates
        # side-by-side from stacked, and it is already computed here.
        def _read_order(q):
            return (int(8 * q["box"][0] / max(1, W)), q["box"][1], q["box"][0])
        for p in sorted(group["panes"], key=_read_order):
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
            cut = draw2.cut_list(p, m.get("size"))
            if cut:
                part = self.part_for("a list of columns", slot)
                part["x0"] = p["box"][0] if part["x0"] is None else min(part["x0"], p["box"][0])
                part["x1"] = p["box"][2] if part["x1"] is None else max(part["x1"], p["box"][2])
                part["model"].add(cut)
                if p.get("_cut_pitch"):
                    self.at(m["ts"], make=True).pitch = p["_cut_pitch"]
                    self.at(m["ts"], make=True).pitch_cut = True
                # AND THE SCREEN CUT THIS WINDOW'S LEFT EDGE. That is the
                # whole gate `cut_list` passed, so it is known here and
                # nowhere else: the window's own corner, its three round
                # buttons and its back and forward arrows all stand outside
                # the frame, and a card that draws them puts on the page
                # what the screen never showed.
                self._cut_left = True
                continue
            part = self.part_for(k, slot)
            part["x0"] = p["box"][0] if part["x0"] is None else min(part["x0"], p["box"][0])
            part["x1"] = p["box"][2] if part["x1"] is None else max(part["x1"], p["box"][2])
            if k == "a list of columns":
                tables = draw2.build_tables(p)
                built = max(tables, key=lambda t: len(t[3])) if tables else None
                # THE FULLER OF THE TWO READINGS OF THE SAME LIST. The
                # reader's own blocks can stop short of the list while every
                # name they dropped is still there in the pane's words:
                # eight rows of sixteen at 00:00:10, the other eight sitting
                # in the pane and drawn nowhere. The rebuild from the words'
                # own positions is taken when it holds MORE rows and all but
                # one of the names the blocks found are among them - more of
                # the list, and nothing of the blocks lost.
                loose = draw2.table_from_loose(p)
                if loose and (not built or len(loose[3]) > len(built[3])):
                    have = {norm(c[0]) for c, _i, _b in (built[3] if built else [])
                            if c and c[0]}
                    got = {norm(c[0]) for c, _i, _b in loose[3] if c and c[0]}
                    if len(have - got) <= 1:
                        built = loose
                if built:
                    part["model"].add(built)
                    # AND WHAT THIS WINDOW'S ROWS REALLY MEASURE at this
                    # moment, taken on the rows that became the list. The
                    # drawing otherwise works the spacing out from a share
                    # held per program, which put the vault-demo Finder at
                    # 81 frame pixels a row where its own rows stand at 65,
                    # and the Finder cut off beside it at 81 where its rows
                    # stand at 42.
                    if len(built) > 8 and built[8]:
                        self.at(m["ts"], make=True).pitch = built[8]
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
                # WHERE THE PANE SAT, kept beside its lines. The lines flow
                # into one model, and a note read in two panes -- the strip
                # above a window in front and the region below it -- flows
                # back out as one column with no room left for what the
                # front window hid, so everything under it lands a quarter
                # of the screen too high. The pane's own box says where its
                # first line stood.
                part["model"].blocks.append((float(p["box"][1]), float(p["box"][3]),
                                             [t for t, _ in pairs]))
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
        self._title_rule()


    def _title_rule(self, again=False):
        """The folder's name, from the window's own furniture. Called
        again once a path bar cut as its own pane has been folded in:
        the rule reads the path, so it must run after the path is there."""
        table = self.main_table()
        # `again` is for the one caller that has just GIVEN this window its
        # path bar. The rule reads the path, so a title settled before the bar
        # arrived was settled on less than the window knows now - and the
        # guard below, which exists to stop a confident title being churned,
        # was refusing the very re-ask its call site asks for. At 00:01:00 it
        # locked `jaredrhodenizer` from a three-crumb path and never looked
        # again when the full bar landed carrying the folder the title bar
        # actually reads.
        if table and (again or not self.title or not getattr(self, "title_sure", False)
                      or getattr(self, "title_from_path", False)):
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
                # ...AND THE OTHER WAY ROUND, WHICH IS THE COMMON ONE. Finder
                # cuts a long folder name short IN ITS TITLE BAR, so the word
                # read there OPENS the crumb rather than the crumb opening it.
                hit = next((t for t, _ in tops
                            if same_text(t, c) or norm(t).startswith(norm(c))
                            or (len(norm(t)) >= 8 and norm(c).startswith(norm(t)))), None)
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
        # A FINDER WITH ITS OWN PATH BAR, STANDING IN A BOX THE FRAME MEASURED,
        # IS A WINDOW HOWEVER FEW ROWS ITS FOLDER HOLDS. At 00:01:10 the
        # `projects` folder lists one item, so its window was a "sliver",
        # never drawn, and the moment had no picture at all - while the frame
        # shows a titled Finder with a five-crumb bar under it. A folder with
        # one file in it is a folder with one file in it.
        if t and len(getattr(t, "path", None) or []) >= 3 and any(True for _ in self.measured):
            return False
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
            # THE SAME FOLDER NAME, READ FROM THE WINDOW ITSELF, IS THE SAME
            # FOLDER. A fragment of it shares the name and little else; the
            # whole list scrolled far enough shares the name and no row at
            # all. Both are the same window - Tristan's rule that a folder
            # scrolled to new content is the same screen extended, not a new
            # one. Measured: the memory folder read at 00:01:20 (its top) and
            # 00:01:30 (scrolled down to the project_ and feedback_ files)
            # share no row name, so row-overlap split them into two cards of
            # one window. The clock keeps two windows showing the SAME folder
            # at the SAME moment apart - those are two windows, and this only
            # merges states that never stood together. A title read off a cut
            # path bar names a folder the path passes THROUGH, not the one on
            # show, so it can never merge.
            titles_match = (self.title and other.title and same_title(self.title, other.title)
                            and not (getattr(self, "title_from_path", False)
                                     or getattr(other, "title_from_path", False)))
            if titles_match and (min(len(a), len(b)) < 3
                                 or not (set(self.times) & set(other.times))):
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


def list_not_tree(states):
    """A Finder list that came back as a file tree, put right.

    A window showing only its Name column - the rest of it off the side
    of the screen or behind another window - has no columns left to
    tell the reader it is a list, and its rows come back as a tree with
    a level of nesting that was never on the screen. The same folder
    names read as a LIST elsewhere in the video say what that window
    is: one window, one program. Nothing is invented - the names are
    the ones that were read, and only what KIND of thing they are in
    changes.
    """
    lists = []
    for st_ in states:
        t_ = st_.main_table()
        if st_.name == "The Finder window" and t_ and len(t_.rows) >= 4:
            lists.append((t_, {fold(flat((r.get("cells") or [""])[0]))
                               for r in t_.rows if (r.get("cells") or [""])[0]}, st_))
    if not lists:
        return
    own = {id(o_) for _t, _k, o_ in lists}
    for st_ in states:
        # ANY window holding a tree whose names are some Finder list's
        # names. Asking only about windows named for the vault left the
        # case the naming rules had ALREADY got right: a window named
        # Finder, drawn with a tree in it and a level of nesting that
        # was never on the screen. A window that is itself one of the
        # lists is not converted - it is the witness.
        if id(st_) in own:
            continue
        # EVERY tree part of the window, not the first. A window can
        # show its own sidebar (a tree of Finder's fixed names, which no
        # list will ever match) and a Finder list beside it that came
        # back as a tree too - and asking only about the first left the
        # second drawn with a level of nesting that was never there.
        for q in [x for x in st_.parts if x["fam"] == "tree"
                  and getattr(x["model"], "lines", None)]:
            _convert_tree(st_, q, lists)

def _convert_tree(st_, q, lists):
    """One tree part put back as the list it really is."""
    names = [row_name(t) for t, _h in q["model"].lines]
    keys = {fold(flat(n)) for n in names if n}
    if len(keys) < 4:
        return
    best, hit, from_ = None, 0, None
    for t_, ks, o_ in lists:
        n = len(keys & ks)
        if n > hit:
            best, hit, from_ = t_, n, o_
    if best is None or hit < max(4, 0.6 * len(keys)):
        return
    head = list(best.header) or ["Name"]
    tab = Table()
    tab.header = head
    tab.span = best.span
    tab.rh = best.rh
    # the same window showing the same folder: its bar and its
    # sidebar were read whole at that other moment, and this one
    # only had them hidden
    tab.path = list(best.path)
    # the readings come across WITH the moments they were read at, which
    # is the whole reason they are one list now
    tab.readings = list(best.readings)
    tab.side = list(best.side)
    by = {fold(flat((r.get("cells") or [""])[0])): r for r in best.rows
          if (r.get("cells") or [""])[0]}
    for n in names:
        if not n:
            return
        src = by.get(fold(flat(n))) or by.get(fold(flat(n)) + "md")
        cells = list(src["cells"]) if src else [n] + [""] * (len(head) - 1)
        if src:
            cells[0] = src["cells"][0]
        tab.rows.append({"cells": cells,
                         "italic": [False] * len(cells),
                         # NOT the band. A file's date and kind are the
                         # same at every moment, so taking them from the
                         # moment this window was read whole is sound -
                         # but WHICH ROW IS SELECTED is the one thing
                         # about a list that changes from moment to
                         # moment. Carried across, it drew `03 Company B
                         # (Landscape Company)` green at 00:01:20, where
                         # the reader records no band at all; the band it
                         # was wearing belongs to 00:02:20. The same
                         # state-against-moment distinction as the path
                         # bar, and no measure can catch this one, since
                         # the green lands on rows the frame drew text
                         # across.
                         "band": None,
                         # a name the list never read whole says nothing
                         # about folder or file: no icon is claimed for it
                         "icon": (src or {}).get("icon")})
    q["fam"] = "table"
    q["model"] = tab
    st_.parts.sort(key=lambda x: x["slot"])
    st_.name = "The Finder window"
    # and the folder it was showing: the window's own title bar,
    # read whole at the moment the window stood clear
    if not st_.title and from_ is not None and from_.title:
        st_.title = from_.title


def _finder_lists(states):
    """Every Finder list with rows enough to be a witness."""
    lists = []
    for st_ in states:
        t_ = st_.main_table()
        if st_.name == "The Finder window" and t_ and len(t_.rows) >= 4:
            lists.append((t_, {fold(flat((r.get("cells") or [""])[0]))
                               for r in t_.rows if (r.get("cells") or [""])[0]}, st_))
    return lists


def convert_probe(probe, states):
    """A moment's window read as a tree, put right BEFORE it is matched
    against the open states - so a Finder whose list came back as a column
    of names joins the window that already lists that folder, instead of
    opening a state of its own that `list_not_tree` only converts after the
    matching is over. Measured: the vault-demo window at 00:00:30 became a
    second card of the same folder that way."""
    if probe.main_table() is not None:
        return
    lists = _finder_lists(states)
    if not lists:
        return
    for q in [x for x in probe.parts if x["fam"] == "tree" and getattr(x["model"], "lines", None)]:
        _convert_tree(probe, q, lists)


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
            convert_probe(probe, states)
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
                else:
                    if m["ts"] not in cur.times:
                        cur.times.append(m["ts"])
                    # THE MOMENT IS KEPT AS A PIECE even when its reading is
                    # too thin to join the window's settled list. Without
                    # it that moment's picture has no reading of its own to
                    # draw from and falls back to the whole window: at
                    # 00:01:00 a window showing two rows of the folder just
                    # opened was drawn holding sixteen rows of the folder
                    # before it. The thin reading still stays OUT of the
                    # settled list, which is what the rule was for.
                    if not any(mm is m for mm, _g in cur.pieces):
                        cur.pieces.append((m, g))
                _sn = cur.at(m["ts"], make=True)
                if _sn.rect is None:
                    _sn.rect = content_rect(cur, g, m)
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
    # A title is a folder's name, and no folder here ends in a bare full
    # stop. `memory.` is the reader's dot, picked up from the title bar of a
    # moving frame; a name that BEGINS with one (`.claude`) is real and is
    # left alone, as is any name whose last stop belongs to an extension
    # (`Vault Index.md` ends in `d`).
    for st in states:
        if st.title and re.search(r"\.{2,}$", st.title):
            # Finder cuts a long title with an ellipsis, which the engines
            # read as two, three or four dots: the screen showed one mark
            st.title = re.sub(r"\.{2,}$", "\u2026", st.title)
        elif st.title and len(st.title) > 1 and st.title.endswith("."):
            st.title = st.title.rstrip(".") or st.title
        # THE BACK AND FORWARD ARROWS BESIDE THE TITLE, read as `<>` in front
        # of it, and the dot-plus-letter the reader hangs on a moving frame's
        # title (`projects.Q`, `>jaredrhodenizer.Q`): neither is a letter of
        # the folder's name. The dot-letter is taken off only where what is
        # left is a crumb of the window's own path bar - the bar spells the
        # folder, so the two readings confirm each other.
        if st.title:
            st.title = re.sub(r"^[<>\u3002\s]+", "", st.title) or st.title
            m_ = re.match(r"^(.+)\.[A-Za-z]$", st.title)
            t_ = st.main_table()
            if m_ and t_ and any(crumb_same(m_.group(1), c) for c in (t_.path or [])):
                st.title = m_.group(1)
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
        # ONE ROW IS NOT "ITS ROWS". This rule renames a window when the rows
        # it lists are the CHILDREN of a known folder - a claim about the body
        # of the list, not about one line of it. With no quorum a single row
        # carried it: the window titled `jaredrhodenizer` lists `.claude`
        # among sixteen names, the settled bars make `.claude` a child of the
        # glued crumb `Usersjaredrhodenizer`, and that one vote renamed a
        # window whose own title bar had been read correctly. The same at the
        # `memory` window, where the single row `MEMORY.md` voted for
        # `-Users-jaredrh`. Five of seventeen pictures were titled after a
        # folder that is on screen in no frame of the video.
        #
        # A window with no title at all still takes a single vote - one guess
        # beats none - and so does a list too short for a quorum to mean
        # anything.
        named = sum(1 for n in t.names() if n)
        if votes[best] < 2 and st.title and named > 2:
            continue
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
    # A GENERIC CRUMB IS ONLY EVER ITSELF. `Users` opens `-Users-jaredrh`
    # and the prefix rule below called them one crumb, so the bar under the
    # memory window was respelt with a folder three levels down standing
    # at its root. The disk, Users, Documents and the home folder are whole
    # names every bar carries; nothing is a longer spelling of them.
    ga, gb = norm(a) in GENERIC, norm(b) in GENERIC
    if ga or gb:
        # the one thing a generic crumb can be besides itself is ITSELF CUT
        # SHORT by Finder or by the reading - `Docur` for `Documents`,
        # `jaredr` for `jaredrhodenizer` - never the head of something longer
        # the generic name is the whole; the other must be SHORTER than it
        if ga and gb:
            g, o = (fa, fb) if len(fa) >= len(fb) else (fb, fa)
        elif ga:
            g, o = fa, fb
        else:
            g, o = fb, fa
        if len(o) >= len(g) or len(o) < 4:
            return False
        return sum(1 for x, y in zip(o, g[:len(o)]) if x != y) <= (0 if len(o) < 5 else 1)
    # A FOLDER AND THE NOTE INSIDE IT NAMED ALIKE ARE TWO CRUMBS. `memory`
    # and `MEMORY.md` flatten to `memory` and `memorymd`, one opening the
    # other, and the rule below took them for one crumb read twice - so the
    # bar under the memory window lost the folder and kept the file, twice.
    if (fa.endswith("md") and fa[:-2] == fb) or (fb.endswith("md") and fb[:-2] == fa):
        return False
    if min(len(fa), len(fb)) >= 4 and abs(len(fa) - len(fb)) <= 10 and (fa.startswith(fb) or fb.startswith(fa)):
        return True
    if (min(len(fa), len(fb)) >= 4 and abs(len(fa) - len(fb)) <= 6 and fa[:3] == fb[:3]
            and difflib.SequenceMatcher(None, fa, fb, autojunk=False).ratio() >= 0.7):
        return True
    k = min(len(fa), len(fb))
    if k >= 12 and (fa.startswith(fb) or fb.startswith(fa)):
        return True             # Finder cuts a long crumb short: `-Users-jaredrh` for `-Users-jaredrhodenizer-Documents-jarvis-demo`
    return k >= 5 and abs(len(fa) - len(fb)) <= 12 and sum(1 for x, y in zip(fa[:k], fb[:k]) if x != y) <= 1




def end_at_folder(path, name):
    """A list window's path bar ends at the folder the window is showing.

    Where that folder's own name was read off the window itself and the bar
    stops short of it, the bar lost its last crumb to the reading and gets
    it back. Where the last crumb opens the same way but reads shorter, that
    crumb IS this folder read badly, and it is corrected rather than
    repeated. A name the path itself supplied is never added back - that
    would be the bar arguing with itself.
    """
    if not path or not name:
        return path
    if any(same_text(c, name) for c in path):
        return path
    last = flat(path[-1])
    if last[:3] == flat(name)[:3] and len(last) < len(flat(name)):
        return list(path[:-1]) + [name]
    return list(path) + [name]

def align_crumbs(mine, whole):
    """One stretch's path bar spelt the way the window's own bar spells it.

    A crumb read here that opens the same way as a crumb over there, is
    longer over there, and appears nowhere in that bar as it stands, is the
    same folder read worse. It takes the better spelling. Nothing is added
    and nothing is dropped - only a name is corrected."""
    out = []
    for c in mine:
        f = flat(c)
        # `Users`, `Documents`, the disk: whole names every bar carries. One
        # of them was "corrected" to `-Users-jaredrh` because that crumb
        # opens with the same letters and the other reading had glued
        # `Users` to the disk - a crumb the video spells the same way
        # everywhere is never a worse spelling of something else.
        if norm(c) in GENERIC:
            out.append(c)
            continue
        if len(f) >= 4 and not any(crumb_same(c, w) for w in whole):
            fits = {w for w in whole if len(flat(w)) > len(f) and flat(w)[:3] == f[:3]
                    and not any(crumb_same(w, m) for m in mine)}
            if len(fits) == 1:
                c = fits.pop()
        out.append(c)
    return out

def mend_path(mine, others):
    """The gaps in one reading of a path bar, filled from another reading of
    the SAME window's bar. Only what sits BETWEEN two crumbs both readings
    carry is filled in: the ancestors of a folder do not change when the
    folder does, so they are revealed, not guessed. Nothing is ever added to
    the end, where the readings genuinely differ."""
    out = list(mine)
    # Before anything is filled in, the crumbs are spelt the way the other
    # readings spell them: a crumb read worse here would otherwise be left
    # standing beside the same folder read better there, as though the two
    # were different folders one inside the other.
    for other in others:
        if other:
            out = align_crumbs(out, other)
    # A path bar starts at the disk. When a reading carries the crumb that
    # every other reading starts from somewhere in the MIDDLE, what sits in
    # front of it was never part of this bar - a neighbouring window's
    # sidebar, read into the same row - and it goes.
    for other in others:
        if not other:
            continue
        j = next((k for k, c in enumerate(out) if crumb_same(c, other[0])), None)
        if j:
            out = out[j:]
            break
    # And where NOTHING at the head lines up but the bar ends at the same
    # folder, the head was never this bar at all - it was read off whatever
    # else stood in that row. The other reading, which does start at the
    # disk, is the bar that stood there.
    for other in others:
        if not other or len(out) < 2 or len(other) < 2:
            continue
        end = next((k for k, c in enumerate(other)
                    if crumb_same(c, out[-1])), None)
        if end is not None and end > 0 \
                and not any(crumb_same(out[0], c) for c in other):
            out = list(other[:end + 1])
            break
    for other in others:
        i = 0
        while i + 1 < len(out):
            ja = next((k for k, c in enumerate(other) if crumb_same(c, out[i])), None)
            jb = next((k for k, c in enumerate(other) if crumb_same(c, out[i + 1])), None)
            if ja is not None and jb is not None and jb > ja + 1:
                # a crumb about to be filled in that opens the same way as
                # the crumb beside it is not a folder of its own: it is that
                # same folder, read better. It corrects the spelling instead
                # of standing next to it as a second folder.
                keep = []
                for c in other[ja + 1:jb]:
                    fc = flat(c)
                    for idx in (i, i + 1):
                        fo = flat(out[idx])
                        if len(fc) >= 4 and len(fo) >= 4 and fc[:3] == fo[:3]:
                            if len(fc) > len(fo):
                                out[idx] = c
                            break
                    else:
                        keep.append(c)
                out[i + 1:i + 1] = keep
                i += len(keep) + 1
            else:
                i += 1
    return out


def unglue(path):
    """A crumb that ENDS with the crumb after it is two crumbs run together.

    One engine reads `Users` and `jaredrhodenizer` as a single word and the
    other reads the second of them on its own, so the bar comes out
    `Macintosh HD > Usersjaredrhodenizer > jaredrhodenizer` where the screen
    shows `Macintosh HD > Users > jaredrhodenizer`. The pair proves itself:
    nothing else explains a crumb whose tail is, letter for letter, the whole
    of its own child. Only the head is kept, and only when a head of real
    length is left over."""
    out = []
    for i, c in enumerate(path):
        nxt = path[i + 1] if i + 1 < len(path) else None
        if nxt and len(c) > len(nxt) + 2 and c.lower().endswith(nxt.lower()):
            head = c[:len(c) - len(nxt)].strip(" -/>")
            if len(head) >= 3:
                c = head
        if out and flat(out[-1]) == flat(c):
            continue                # the same crumb twice running: once
        # the reader's own full stop on the end of a crumb (`memory.`),
        # never part of a folder's name; `...` marks a cut and stays
        if len(c) > 2 and c.endswith(".") and not c.endswith(".."):
            c = c[:-1]
        # and its dot-plus-capital (`projects.Q`), read off a moving frame:
        # no folder in this video ends in a one-letter capital extension
        m_ = re.match(r"^(.{4,})\.[A-Z]$", c)
        if m_:
            c = m_.group(1)
        out.append(c)
    return out


def chain_paths(paths):
    """Partial readings of one path bar joined: the longest read is the
    spine, and crumbs the other reads carry between its anchors slot in
    where they sat."""
    paths = [p for p in paths if p]
    if not paths:
        return []
    base = list(max(paths, key=len))
    # every reading spelt the way the fullest reading spells it, before any
    # of them is slotted in: otherwise one reading's worse spelling of a
    # crumb stands beside the other's better one as a second folder
    paths = [p if p is base else align_crumbs(p, base) for p in paths]
    for p in paths:
        if p == base:
            continue
        # a path bar starts at the disk: where a shorter reading carries the
        # crumb the longest one starts from somewhere in its middle, what sits
        # in front of it belongs to something else on the screen - a
        # neighbouring window's sidebar read into the same row - and is dropped
        # rather than merged in front of the root
        j = next((k for k, c in enumerate(p) if crumb_same(c, base[0])), None)
        if j:
            p = p[j:]
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
    title_flats = {flat(st.title) for st in states if st.title}
    crumb_flats = {flat(c) for st in states for q in st.parts
                   if q["fam"] == "table" for c in (q["model"].path or [])}
    # how many WINDOWS spell a crumb this way: a spelling two bars agree on
    # is the folder's name; one bar's own reading proves nothing about itself
    _voices = {}
    for st in states:
        for q in st.parts:
            if q["fam"] == "table":
                for f_ in {flat(c) for c in (q["model"].path or [])}:
                    _voices.setdefault(f_, set()).add((st.name, flat(st.title or "")))
    crumb_votes = {f_: len(v_) for f_, v_ in _voices.items()}
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
                        b = b.lstrip("│ ˃˅")             # a name, never the row's own marks
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
                    # ONE ENGINE GLUES `Users` TO THE FOLDER AFTER IT, and the
                    # completion below then "finishes" `Usersjaredrhodenizer`
                    # into the longest name that opens with those letters -
                    # a folder three levels down. The glue is cut first: a
                    # crumb opening with a generic crumb whose remainder is a
                    # name the video knows whole is those two crumbs.
                    known_flat = strong_flats | row_flats | {flat(c_) for c_ in clean}
                    settled_flat = strong_flats | row_flats
                    split_ = []
                    for c in path:
                        f = flat(c)
                        done = False
                        # ...UNLESS THIS WINDOW'S OWN BAR READ THE CRUMB LONGER
                        # at another moment: `-Users-jaredrh` is Finder's own
                        # cut of `-Users-jaredrhodenizer-Documents-jarvis-demo`,
                        # read whole at 00:01:30, and splitting it into `Users`
                        # and `jaredrh` threw the folder away for good.
                        own_longer = any(crumb_same(c, w) and len(flat(w)) > len(f)
                                         for p_ in (getattr(table, "paths", None) or []) for w in p_)
                        if f not in settled_flat and len(f) >= 10 and not own_longer:
                            for g_ in ("users", "documents", "desktop", "downloads"):
                                rest_ = f[len(g_):]
                                if f.startswith(g_) and rest_ in known_flat and len(rest_) >= 4:
                                    split_.append(g_.capitalize())
                                    split_.append(canon.get(rest_) or canon_fold.get(fold(rest_)) or c[len(g_):])
                                    done = True
                                    break
                        # ...AND A CHEVRON THE READER DROPPED leaves two crumbs
                        # in one, `.claude projects`: two names the video knows
                        # whole with a space between them are two crumbs.
                        if not done and " " in c.strip() and f not in settled_flat:
                            bits_ = c.split()
                            if len(bits_) >= 2 and all(flat(x_) in known_flat for x_ in bits_):
                                split_.extend(bits_)
                                done = True
                        if not done:
                            split_.append(c)
                    path[:] = split_
                    for i, c in enumerate(path):
                        c = mend_numbered(c, strong_names)    # o3 is a nought
                        path[i] = c
                        f = flat(c)
                        b = exact_fix(c)
                        # A CRUMB SOME WINDOW'S TITLE BAR OR ANOTHER BAR SPELLS
                        # THIS WAY IS NOT A MISREADING: `projects` stood in a
                        # title and in every bar, and was "corrected" into the
                        # one row that read `projerts`.
                        if (not b and len(f) >= 6 and f not in strong_flats and f not in row_flats
                                and f not in title_flats and crumb_votes.get(f, 0) < 2):
                            # a crumb misread by a letter or two (`prjects`,
                            # `jaredrhodenize`) takes the name the video
                            # spells whole, when exactly one strong name
                            # reads that close
                            _c0 = lambda ch: {"o": "0", "i": "1", "l": "1"}.get(ch, ch)
                            near = [p_ for p_ in strong_names
                                    if abs(len(flat(p_)) - len(f)) <= 2 and _c0(flat(p_)[:1]) == _c0(f[:1])
                                    and difflib.SequenceMatcher(None, flat(p_), f, autojunk=False).ratio() >= 0.85]
                            if len({flat(p_) for p_ in near}) == 1:
                                b = near[0]
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
                                return sum(1 for x, y in zip(head, f) if x != y) <= (0 if len(f) < 5 else 1)
                            # only a name read whole somewhere can finish a
                            # crumb, and the shortest such name is the folder
                            # Finder cut short -- a longer one is a different file
                            starts = [p for p in strong_names if opens(p)]
                            exact = [p for p in starts if flat(p).startswith(f)]
                            starts = exact or starts      # a clean opening beats a slipped one
                            # A GENERIC CRUMB IS NEVER COMPLETED INTO A FOLDER
                            # BELOW IT. `Users` opens `-Users-jaredrh`; the only
                            # completion a generic crumb may take is the generic
                            # name it was cut from (`jaredr` -> `jaredrhodenizer`).
                            if norm(c) in GENERIC:
                                starts = [p for p in starts if norm(p) in GENERIC]
                            elif len(f) <= 7:
                                # a short crumb completes only into a folder
                                # some window was seen standing in - a title
                                # or another bar's crumb - never into a file
                                # name that happens to open the same way
                                starts = [p for p in starts
                                          if flat(p) in title_flats or flat(p) in crumb_flats]
                            if starts:
                                b = min(starts, key=lambda p: len(flat(p)))
                        if b:
                            path[i] = b
                # the crumbs read at ONE moment chain into the one bar the
                # window carried then (each partial read skipped what its
                # engines missed: at 00:03:30 one engine gave `Macintosh HD |
                # Users | Docum> | vault-c >` and another `jaredrh> | 02Con>`,
                # halves of the same bar).
                #
                # ACROSS moments they must not chain. A window navigates: the
                # same Finder stood in `.claude/projects` at 00:00:50 and in
                # `vault-demo/02 Company A` at 00:03:00, and chaining welded
                # the two into `Macintosh HD > Users > jared > .claude >
                # prjects > Documents > vault-demo > 02 Company A` - a path
                # that never existed. So chain within the LATEST moment that
                # read a bar, and let that bar stand alone.
                late = [p for t, p in table.readings
                        if t is not None and t == max((x for x, _ in table.readings if x is not None),
                                                      default=None)]
                table.path = chain_paths(late if late else [table.path] + table.paths)
                # The latest bar is spelt the way this window's own reads
                # spell the same folders. Splitting by moment can leave the
                # last moment holding a cut-short read - `Docur`, `02 Con` -
                # where another moment read that folder whole. `align_crumbs`
                # will not do it: it only corrects a crumb it finds ABSENT
                # from the other bar, and `Docur` already matches `Documents`
                # there. Correcting a spelling adds no crumb and drops none;
                # a folder does not rename itself between two frames.
                for i, c in enumerate(table.path):
                    best_c = c
                    for other in table.paths:
                        for w in other:
                            if (crumb_same(c, w) and len(flat(w)) > len(flat(best_c))
                                    and flat(w).startswith(flat(c)[:3])):
                                best_c = w
                    table.path[i] = best_c
                # and the crumbs one engine ran together are separated here
                # too: this path was chained and re-spelt after `Table.add`
                # saw it, so a glue can be reassembled on the way through.
                table.path = unglue(table.path)
                # THE BAR ENDS AT THE FOLDER THE TITLE BAR NAMES, and it is
                # put there HERE because this is where the bar is rebuilt
                # from its readings: every later pass that rebuilt it threw
                # the folder away again, so `Assets` stood in the window's
                # title and never at the end of its bar.
                if st.title and not getattr(st, "title_from_path", False) and st.name == "The Finder window":
                    table.path = end_at_folder(table.path, st.title)
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
    # EVERY LIST, ON EVERY PASS: a name loses the reader's full stop, a kind
    # is spelt as Finder spells it, a row read twice is one row, and a row
    # name one letter off a folder name the video agrees on - a title, or a
    # crumb two windows' bars spell alike - takes that spelling. `projerts`
    # stood in the .claude list under a bar and a title that both read
    # `projects`.
    agreed = {}
    _c0a = lambda ch: {"o": "0", "i": "1", "l": "1"}.get(ch, ch)
    for st in states:
        if st.title:
            agreed.setdefault(flat(st.title), st.title)
    for st in states:
        for q in st.parts:
            if q["fam"] == "table":
                for c_ in (q["model"].path or []):
                    if crumb_votes.get(flat(c_), 0) >= 2:
                        agreed.setdefault(flat(c_), c_)
    def _agreed_form(text_):
        """The agreed spelling of a name that is the agreed name after flat
        (`(info Product)` for `(Info Product)`): the one with its capitals."""
        k_ = flat(text_)
        v_ = agreed.get(k_)
        if v_ and v_ != text_ and sum(ch.isupper() for ch in v_) > sum(ch.isupper() for ch in text_):
            return v_
        return text_

    def _agreed_near(text_):
        """An agreed folder name one or two letters off this one, O and 0,
        l and 1 counted alike; None where none or more than one."""
        f_ = flat(text_)
        if len(f_) < 6 or f_ in agreed:
            return None
        near_ = {v for k_, v in agreed.items() if len(k_) == len(f_) and _c0a(k_[:1]) == _c0a(f_[:1])
                 and sum(1 for u, w in zip(k_, f_) if _c0a(u) != _c0a(w)) <= 2}
        return next(iter(near_)) if len({flat(v) for v in near_}) == 1 else None
    for st in states:
        if st.title:
            st.title = _agreed_form(st.title)
        for q in st.parts:
            if q["fam"] == "tree" and getattr(q["model"], "lines", None):
                # a tree row one letter off an agreed folder name is that folder
                new_ = []
                for t, h in q["model"].lines:
                    nm_ = row_name(t)
                    rep_ = _agreed_near(nm_) or _agreed_form(nm_)
                    if rep_ and rep_ != nm_:
                        lead_ = t[:len(t) - len(t.lstrip("\u2502 \u02c3\u02c5"))]
                        new_.append((lead_ + rep_, h))
                    else:
                        new_.append((t, h))
                q["model"].lines = new_
            if q["fam"] != "table":
                continue
            t_ = q["model"]
            if t_.path:
                t_.path = [_agreed_form(c_) for c_ in t_.path]
            ki_ = next((i for i, h in enumerate(t_.header) if h and "Kind" in h), None)
            # TWO ROWS READ AS ONE NAME: `My Product Opdsations` over a date
            # cell holding two dates, beside rows `My Product` and
            # `Operations` - the glue is dropped, both rows stand
            drop_glued(t_)
            # A CRUMB FINDER CUT SHORT, ON THE WINDOW'S OWN CARD, IS THE
            # FOLDER'S WHOLE NAME where the video agrees on exactly one:
            # `02 Co` under the Assets window is `02 Company A (Info Product)`.
            # The pictures keep the cut, which is what their frames show.
            if t_.path:
                for i_, c_ in enumerate(t_.path):
                    f_ = flat(c_)
                    if len(f_) >= 4 and f_ not in agreed:
                        longer_ = {v for k_, v in agreed.items() if k_.startswith(f_) and len(k_) > len(f_)}
                        if len({flat(v) for v in longer_}) == 1:
                            t_.path[i_] = next(iter(longer_))
                            continue
                        # `O2CompanyA(InfoProduct)` for `02 Company A (Info Product)`:
                        # one letter the reader cannot tell from a digit
                        near_ = {v for k_, v in agreed.items() if len(k_) == len(f_) and _c0a(k_[:1]) == _c0a(f_[:1])
                                 and sum(1 for u, w in zip(k_, f_) if u != w) <= 2}
                        if len({flat(v) for v in near_}) == 1:
                            t_.path[i_] = next(iter(near_))
            for r in t_.rows:
                if r["cells"] and r["cells"][0]:
                    r["cells"][0] = _agreed_form(bare_dot(r["cells"][0]))
                    f_ = flat(r["cells"][0])
                    if len(f_) >= 6 and f_ not in agreed and "." not in r["cells"][0]:
                        near_ = [v for k_, v in agreed.items() if abs(len(k_) - len(f_)) <= 1 and _c0a(k_[:1]) == _c0a(f_[:1])
                                 and difflib.SequenceMatcher(None, k_, f_, autojunk=False).ratio() >= 0.85]
                        if len({flat(v) for v in near_}) == 1:
                            r["cells"][0] = near_[0]
                            if r.get("italic"):
                                r["italic"][0] = False
                if ki_ is not None and ki_ < len(r["cells"]) and r["cells"][ki_]:
                    r["cells"][ki_] = canon_kind(r["cells"][ki_])
            fold_twins(t_, 0)
    complete_docs(states)


# ------------------------------------------------------------- the screen itself
#
# A moment picture is the whole screen at the size the video had it: every
# window where it sat, the one being shown filled with what it held over
# that stretch of time, the others as empty outlines. Its content comes
# only from the moments inside the stretch, so it stays an honest still.

def card_shot(html, ratio, share=None, tree_min=None):
    """A rebuilt window given the SHAPE it really had, as a floor.

    The moment pictures bind every window to its own measured width; the
    per-window sections below carried no such constraint at all - page width,
    and whatever height the content needed - so one window stood at 0.86,
    3.74, 3.74 and 0.48 across its four sections, a spread of 7.8x, each of
    them 2.2 to 3.5 times off the shape it really had (Run 19x).

    The window's real proportion is a FLOOR here and never a ceiling. These
    sections exist to be read, and they hold everything gathered across every
    moment the window showed the same thing - which is legitimately more than
    the window held at once. So a card may be taller than its window's shape
    and must never be shorter, and it is never clipped: clipping is what would
    make "rebuilt to read" a lie.

    The regex takes the window's opening tag only where it has no style
    attribute of its own. ONE STYLE ATTRIBUTE, NOT TWO - a second one is
    silently ignored by every browser, which cost three afternoons of changes
    that scored exactly identical.
    """
    if not ratio or ratio <= 0 or "sn-window" not in html:
        return html
    # THE SHAPE IS A RATIO, NOT A PIXEL COUNT. It was written as
    # `min-height:673px`, worked out against a 960px card - so the moment the
    # reading pane stopped being 960 wide, every proportion was wrong: at
    # 1500px that same card stands at 0.45 where the window stood at 0.70.
    # A floor in pixels is only correct at one width, and the width is the
    # reader's to choose.
    #
    # `--sn-ratio` is height over width, and the stylesheet turns it into a
    # floor with a percentage-padding pseudo-element, because PERCENTAGE
    # PADDING RESOLVES AGAINST WIDTH. That gives height >= ratio x width at
    # ANY width, while content taller than the shape still makes the card
    # taller -- which is the rule these sections run on: the window's
    # proportion is a floor and never a ceiling, and nothing is ever clipped.
    # `aspect-ratio` was the obvious tool and is the wrong one: it fixes the
    # height outright, and `.sn-window` sets `overflow:hidden`, so anything
    # past the shape would be silently cut off.
    #
    # `max-width` is the window's own share of the SCREEN. A window that took
    # a third of the desktop was being drawn as wide as one that filled it,
    # which is the same fault as the height and reads worse, because side by
    # side the two look like the same window.
    bits = ["--sn-ratio:%.4f" % ratio]
    # THE SHARE BELONGS TO A PICTURE, NOT TO A CARD. Capping a card at its
    # window's share of the screen was measured, was correct, and made the
    # cards WORSE -- because it answers a question a card does not ask. On a
    # screen, relative size is information: two windows side by side, one twice
    # the other, and the picture has to show that. A card holds ONE window with
    # nothing beside it to compare against, so the share buys nothing there and
    # spends the only thing a card is for, which is room to read. Computed and
    # deliberately unused here; the picture is where it belongs.
    _unused_share = share
    if tree_min:
        # THE FILE TREE, WIDE ENOUGH TO READ -- ON THE CARD ONLY. Its column is
        # a share of the window measured off the frame, and that share is
        # right: at 00:00:00 Obsidian stands full screen with its sidebar at
        # 392 of 3840 pixels, a true 10%. But 10% of a 3840px screen is 392px
        # and shows every name, where 10% of a 700px card is 70px and shows
        # none. The picture keeps the true share; the card, which exists to be
        # READ, floors the column at the width its own longest row needs.
        bits.append("--sn-tree-min:%s" % tree_min)
    return re.sub(r'^(<div class="sn-window[^"]*")(?=>)',
                  r'\1 style="%s"' % ";".join(bits),
                  html, count=1)


CARD_W = 960          # the canvas the note's own stylesheet is drawn against


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
    # A MOMENT THE FRAME MEASURED KEEPS ITS OWN RECTANGLE. This rule is for
    # a moment whose box was worked out from where words sat; run over a
    # measured one it carries a neighbouring moment's shape onto a window
    # the frame plainly drew smaller - one window came out 256 pixels wider
    # than its own edge, with clear desktop beside it in the frame.
    tsx = [t for t in state.rects if t not in state.measured]
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
                state.at(t, make=True).rect = list(big)
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
            if i is None or ts in st.measured:
                continue      # the frame measured this moment; it stands
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
                        _sn = st.at(ts, make=True)
                        _sn.rect, _sn.measured = list(big), True
                        r = _sn.rect


def content_rect(state, group, m):
    """Where the window sat, in frame pixels: the reader's measurement when
    it made one, else the box around the content this window actually drew
    -- words from a window behind, which the reader read on the same pane,
    stay out of it."""
    items = [it for p in group.get("panes") or [] for it in draw2.items_of(p) if it["text"].strip()]
    if not items:
        return list(group.get("rect") or [0, 0, 0, 0])
    W, H = (m.get("size") or [1920, 1080])[:2]
    # THE READER ALREADY SAID WHICH WINDOW THESE PANES BELONG TO. Each pane
    # carries the number of the window it was cut from, and that window's
    # rectangle was measured off the frame. Deciding it again here - by
    # counting how many words fall inside the rectangle - answers wrongly
    # whenever a window's own path bar sits below its measured edge or a
    # pane holds words showing through from behind, and the box then falls
    # back to the bounding box of the words: a window drawn 84 pixels short
    # of where the screen had it. A measured rectangle outranks anything
    # worked out from words, and the number saying WHICH rectangle is the
    # pane's own.
    filed = collections.Counter(p_.get("wi") for p_ in group.get("panes") or []
                                if p_.get("wi") is not None)
    if filed:
        wi = filed.most_common(1)[0][0]
        for w in m.get("windows") or []:
            if w.get("wi") == wi and w.get("rect"):
                state.at(m["ts"], make=True).measured = True
                return [float(v) for v in w["rect"]]
    for w in m.get("windows") or []:
        r = w.get("rect")
        if not r:
            continue
        inside = sum(1 for it in items
                     if r[0] - 20 <= it["box"][0] and it["box"][2] <= r[2] + 20
                     and r[1] - 20 <= it["box"][1] and it["box"][3] <= r[3] + 20)
        if inside >= 0.6 * len(items):
            state.at(m["ts"], make=True).measured = True
            return [float(v) for v in r]
    rh = max(12.0, (sum(it["box"][3] - it["box"][1] for it in items) / len(items)) * 1.6)
    plain = [min(it["box"][0] for it in items), min(it["box"][1] for it in items),
             max(it["box"][2] for it in items), max(it["box"][3] for it in items)]
    # a window whose words sit where they sat a moment ago has not moved, so
    # its edges are the edges already measured: the picture of the screen is
    # only read again when something about the window actually changed
    # THE MOMENT BEFORE THIS ONE, ASKED FOR BY NAME. This used to read a bare
    # `_stood` on the window, which held whatever moment ran last against that
    # object -- so the same frame got a different answer during the main build
    # than during a stretch's replay, because the two visit moments in
    # different company. A window has not moved if its words sit where they sat
    # AT THE MOMENT BEFORE, and that is now what is compared.
    was = state.stood_before(m["ts"])
    if was and all(abs(a - b) <= 0.015 * W for a, b in zip(plain[::2], was[0][::2])) \
            and all(abs(a - b) <= 0.015 * H for a, b in zip(plain[1::2], was[0][1::2])):
        if was[2]:
            state.at(m["ts"], make=True).measured = True
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
            state.at(m["ts"], make=True).measured = True
        state.at(m["ts"], make=True).stood = (plain, drawn, sure)
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
    state.at(m["ts"], make=True).stood = (plain, box, False)
    return box


BORROWED = collections.Counter()    # where a shape came from another moment


def rect_at(st, ts):
    """Where this window stood at ONE moment, AND WHERE THE ANSWER CAME FROM.

        ("measured", box)  the reader measured this window's own edges here
        ("read", box)      worked out from what the window drew at this moment
        ("borrowed", box)  NOTHING WAS RECORDED FOR THIS MOMENT -- the box is
                           another moment's, carried in
        (None, None)       nothing to give

    THE THIRD ONE IS THE POINT. Every site that wanted a shape used to write
    `st.rects.get(ts) or st.rect`, and that `or` silently answered "what did
    this window look like at 00:01:20" with the shape it had at 00:00:00.
    Measured on the memory-files video, that fallback answers 18 times, so it
    is not a theoretical hole. Text encoding has drawn this line since TEI P5:
    a GAP -- not read here, carrying its reason -- is a different thing from a
    reading, and neither may be quietly turned into the other. Occupancy grids
    draw it a second way and never let unobserved collapse into free.

    The borrow still happens where a site chooses it; what it may no longer do
    is happen invisibly."""
    sn = st.at(ts)
    if sn is not None and sn.rect:
        return ("measured" if sn.measured else "read"), sn.rect
    if st.rect:
        BORROWED[ts] += 1
        return "borrowed", st.rect
    return None, None


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
    _how, here = rect_at(st, ts)
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
    out._parent = st        # the whole window, for what this stretch never read tightly
    # A TITLE IS A PROPERTY OF THE MOMENT, NOT OF THE WINDOW. This slice holds
    # only its own stretch's reading, and `label_for` already says a window
    # that opens a different folder later must not be named here by the folder
    # it opened later - the name drawn in the window's own title bar owes the
    # same. At 00:01:00 the state reaches back to 00:00:10, when that window
    # listed `jaredrhodenizer`, and the slice wore that name over a stretch
    # showing another folder entirely. Asked of its OWN table the slice works
    # out its own name; the state's stands only where the slice cannot.
    _inherited = out.title
    out._title_rule(again=True)
    if not out.title:
        out.title, out.title_sure = _inherited, getattr(st, "title_sure", False)
    elif (_inherited and norm(flat(_inherited)) == norm(flat(out.title))
            and len(_inherited) > len(out.title)):
        # THE SAME FOLDER, SPELT BETTER BY THE WHOLE WINDOW. The slice reads
        # only its own moments, so where it names the same folder it can name
        # it worse - at 00:03:50 it gave `02Company A (Info Product)` for the
        # `02 Company A (Info Product)` the window reads across its whole
        # stretch. Same name, so the fuller spelling stands; a DIFFERENT name
        # is the slice's to give, which is the whole point of asking it.
        out.title = _inherited
    out.said = [(ts, s) for ts, s in st.said if t0 <= ts <= t1]
    out.of = st
    # a stretch reads the path bar in whatever pieces that stretch showed;
    # the window's own fuller reading fills the gaps, so the bar under a
    # picture says what the bar under the window's own card says
    here, whole = out.main_table(), st.main_table()
    if here and here.path and whole and whole.path:
        here.path = mend_path(here.path, [whole.path])
        # the bar ends at the folder this window is showing, which does not
        # change across the stretch. What the whole window's bar carries
        # BEYOND that is a row that happened to be selected at some other
        # moment, and Finder puts the selected row on the end - so the
        # folder comes across and nothing else does
        if not getattr(st, "title_from_path", False):
            here.path = end_at_folder(here.path, st.title)
        # the window's own bar may carry the folder's name where this
        # stretch's reading lost it. Only the folder crosses over: anything
        # further along is a row that was selected at some other moment
        extra = whole.path[len(here.path):]
        if len(extra) == 1 and st.title and same_text(extra[0], st.title) \
                and all(crumb_same(a, b) for a, b in zip(here.path, whole.path)):
            here.path = list(here.path) + [extra[0]]
    # A stretch reads the tree in whatever pieces it showed, sometimes as a
    # bare column of names with no shape at all. The window's own tree puts
    # those rows back where they stood.
    mend_slice_tree(out, st)
    return out


def drop_glued(t_):
    """Two rows read as one name - `My Product Opdsations` over a date cell
    holding two dates, beside rows `My Product` and `Operations` - the glue
    is dropped and both rows stand."""
    names_ = [r["cells"][0] for r in t_.rows if r["cells"] and r["cells"][0]]
    di_ = next((i for i, h in enumerate(t_.header) if h and "Date" in h), None)
    kept_ = []
    for r in t_.rows:
        nm_ = r["cells"][0] if r["cells"] else ""
        dc_ = r["cells"][di_] if (di_ is not None and di_ < len(r["cells"])) else ""
        two_ = len(re.findall(r"\d{4}", dc_ or "")) >= 2
        heads_ = [o_ for o_ in names_ if o_ != nm_ and nm_.startswith(o_ + " ")]
        tail_ok = False
        for h_ in heads_:
            tail_ = norm(nm_[len(h_):])
            tail_ok = tail_ok or any(o_ != nm_ and o_ != h_ and len(norm(o_)) >= 5 and abs(len(norm(o_)) - len(tail_)) <= 2
                                     and difflib.SequenceMatcher(None, norm(o_), tail_, autojunk=False).ratio() >= 0.7
                                     for o_ in names_)
        if heads_ and (two_ or tail_ok):
            continue
        kept_.append(r)
    t_.rows = kept_


def respell_from(sl, st):
    """A stretch's own reading of a name, a title or a tree row takes the
    window's settled spelling where the two are one word - equal after
    norm, or a letter or two apart on the same length - because the
    settled one was voted across every moment and keeps its spaces and
    punctuation: `03 CompanyB(LandscapeCompany)` reads as `03 Company B
    (Landscape Company)`, `Opekations` as `Operations`."""
    def score_(s_):
        return (sum(1 for ch in s_ if not ch.isalnum()), sum(ch.isupper() for ch in s_), len(s_))

    def close_(a_, b_, same_rest=False):
        x_, y_ = norm(a_), norm(b_)
        if not x_ or not y_:
            return False
        if x_ == y_:
            return True
        if min(len(x_), len(y_)) < 5 or abs(len(x_) - len(y_)) > 2:
            return False
        ratio_ = difflib.SequenceMatcher(None, x_, y_, autojunk=False).ratio()
        return ratio_ >= (0.8 if same_rest else 0.88)

    def pick_(mine_, settled_):
        if norm(mine_) == norm(settled_):
            return settled_ if score_(settled_) >= score_(mine_) else mine_
        return settled_
    t_, w_ = sl.main_table(), st.main_table()
    named_ = bool(t_ and t_.header and t_.header[0] and "Name" in t_.header[0])
    if t_ and w_ and t_ is not w_ and named_:
        for r in t_.rows:
            nm_ = r["cells"][0] if r["cells"] else ""
            if not nm_ or GLUED_SIZE.search(nm_) or GLUED_DATE.search(nm_):
                continue
            def _rest_same(o_):
                a_ = [norm(c) for c in r["cells"][1:] if c]
                b_ = [norm(c) for c in o_["cells"][1:] if c]
                return len(a_) >= 2 and all(c in b_ for c in a_)
            hit_ = next((o["cells"][0] for o in w_.rows if o["cells"] and o["cells"][0]
                         and close_(nm_, o["cells"][0], _rest_same(o))), None)
            if hit_ and hit_ != nm_:
                r["cells"][0] = pick_(nm_, hit_)
    if sl.title and st.title and sl.title != st.title and close_(sl.title, st.title):
        sl.title = pick_(sl.title, st.title)
    a_, b_ = sl.tree(), st.tree()
    if a_ and b_ and a_ is not b_:
        new_ = []
        for t, h in a_.lines:
            nm_ = row_name(t)
            hit_ = next((row_name(u) for u, _ in b_.lines if close_(nm_, row_name(u))), None)
            if hit_ and hit_ != nm_:
                rep_ = pick_(nm_, hit_)
                lead_ = t[:len(t) - len(t.lstrip("\u2502 \u02c3\u02c5"))]
                new_.append((lead_ + rep_, h))
            else:
                new_.append((t, h))
        a_.lines = new_


def mend_slice_tree(sl, st):
    """Put this stretch's tree rows back into the shape the window's own
    tree gives them. Run last, after every pass that drops or rewrites a
    line: those passes judge a row on its own, and a row of a tree is only
    as good as the rows it hangs from."""
    mine, all_of = sl.tree(), st.tree()
    if mine is None and all_of is not None:
        # THIS STRETCH READ THE TREE AS A PLAIN COLUMN OF NAMES. Nothing in
        # the pane said "tree", so the names went to a document part and the
        # picture drew no tree at all - two of eighteen pictures showed the
        # Obsidian window with its whole left column empty, although the
        # names were read and are in the record. The window's own tree says
        # what shape they stood in; only the rows THIS stretch read are
        # kept, so nothing is drawn that was not on the screen.
        for q in sl.parts:
            if q["fam"] != "doc" or not getattr(q["model"], "lines", None):
                continue
            names = {fold(flat(row_name(t))) for t, _h in q["model"].lines}
            names.discard("")
            hit = [ln for ln in all_of.lines
                   if fold(flat(row_name(ln[0]))) in names]
            if len(hit) >= max(4, 0.5 * len(q["model"].lines)):
                tree = Lines("a file tree")
                tree.lines = list(hit)
                q["fam"] = "tree"
                q["model"] = tree
                sl.parts.sort(key=lambda x: x["slot"])
                return
    if mine is not None and all_of is not None and mine is not all_of:
        # THE ROWS THIS STRETCH READ ARE THE ROWS ON ITS SCREEN. The mend
        # hangs them on the window's whole tree, which also brings in every
        # row above and below them - at 00:04:10 the explorer stood scrolled
        # to `feedback_subject_line...` and the picture drew the tree from
        # its top. The mended tree is cut back to the stretch's own first
        # and last rows.
        first_ = fold(flat(row_name(mine.lines[0][0]))) if mine.lines else ""
        last_ = fold(flat(row_name(mine.lines[-1][0]))) if mine.lines else ""
        merged_ = mend_tree(mine.lines, all_of.lines)
        keys_ = [fold(flat(row_name(t))) for t, _ in merged_]
        i0 = keys_.index(first_) if first_ in keys_ else 0
        i1 = (len(keys_) - 1 - keys_[::-1].index(last_)) if last_ in keys_ else len(keys_) - 1
        mine.lines = merged_[i0:i1 + 1] if i1 >= i0 else merged_


def row_name(t):
    """A tree row's name, without the guides and the open/shut mark."""
    return t.lstrip("│ ˃˅").strip()


def row_mark(t):
    """A tree row's open-or-shut mark, or empty where it has none."""
    lead = t[:len(t) - len(t.lstrip("│ ˃˅"))]
    for ch in reversed(lead):
        if ch in "˃˅":
            return ch
    return ""


def set_mark(t, ch):
    """The same row with its open-or-shut mark changed, guides untouched."""
    lead = t[:len(t) - len(t.lstrip("│ ˃˅"))]
    rest = t[len(lead):]
    out, done = [], False
    for c in reversed(lead):
        if not done and c in "˃˅":
            out.append(ch)
            done = True
        else:
            out.append(c)
    return "".join(reversed(out)) + rest


def row_depth(t):
    """How deep a tree row hangs, counted off its guides."""
    return t[:len(t) - len(t.lstrip("│ ˃˅"))].count("│")


def mend_tree(mine, whole):
    """A stretch's tree rows put back into the shape the window's own tree
    says they had.

    Three things are restored and nothing else. Each row takes its true
    depth and its open-or-shut mark. Rows the whole tree places BETWEEN two
    rows this stretch read are filled in - the same law the path bars keep,
    that only what sits between two things you carry is ever filled. And
    the chain of parents above the first row comes back, because a row
    cannot stand on the screen unless the rows it hangs from stand open
    above it.

    Rows that had scrolled off above or below are NOT brought back: the
    picture is of a stretch, and a row nothing in that stretch showed is
    not part of it.
    """
    if not mine or not whole:
        return mine
    def key_of(t):
        # a name cut short by the pane's edge is the same name: the dots
        # that say it was cut are not part of it
        return fold(flat(row_name(t).rstrip(".…")))
    keys = [key_of(t) for t, _ in whole]
    where = {}
    for i, k in enumerate(keys):
        where.setdefault(k, i)

    def alike(a, b):
        """The same name, one of them cut short by the pane's edge."""
        if a == b:
            return True
        return (len(a) >= 10 and len(b) >= 10
                and (a.startswith(b) or b.startswith(a)))

    def find(k, after=0):
        """The row of the whole tree this reading is of, cut short or not.

        A tree carries the same name twice over - a folder and the note
        inside it are named alike, and Jared's vault is full of them - so
        a name on its own cannot say WHICH row was read. The order the
        rows stand in can, and both lists stand in screen order, so the
        search runs on from the last row matched and only falls back to
        the top when nothing below fits."""
        for i in range(after, len(keys)):
            if alike(k, keys[i]):
                return i
        for i in range(0, min(after, len(keys))):
            if alike(k, keys[i]):
                return i
        return None
    # two rows the reader ran into one line are two rows again, when the
    # window's own tree carries both of them, one after the other
    split = []
    for t, h in mine:
        k = key_of(t)
        if find(k) is None:
            for i in range(len(whole) - 1):
                a = key_of(whole[i][0])
                b = key_of(whole[i + 1][0])
                if len(a) >= 6 and len(b) >= 6 and k == a + b:
                    split.extend([whole[i], whole[i + 1]])
                    break
            else:
                split.append((t, h))
            continue
        split.append((t, h))
    mine = split
    hits, walk, mark = [], 0, {}
    for t, _ in mine:
        i = find(key_of(t), walk)
        if i is not None:
            hits.append(i)
            mark[i] = row_mark(t)
            walk = i + 1
    if len(hits) < 0.6 * len(mine) or len(hits) < 3:
        return mine                       # not the same tree; leave it alone

    def parents(i):
        """The chain of rows the row at i hangs from. A row hangs from the
        nearest row above it that is shallower, or - where the reader read
        every name at one depth - from the nearest folder above it standing
        open, since a shut folder shows nothing underneath it."""
        want = row_depth(whole[i][0])
        for j in range(i - 1, -1, -1):
            t = whole[j][0]
            d = row_depth(t)
            if d < want:
                yield j
                want = d
            elif d == want and row_name(t) and t.lstrip("│ ")[:1] == "˅":
                yield j
                want = d - 1
            if want < 0:
                return

    # Only what this stretch showed, and the rows it hung from. Nothing is
    # filled in between: a folder standing shut shows none of its files,
    # and a row the whole tree carries because some other moment opened
    # that folder was not on the screen now.
    take = set(hits)
    for i in list(take):
        take.update(parents(i))
    # Depth is the tree's own and never changes, so it comes from the whole
    # tree. Whether a folder stood open does change - that is the whole
    # point of a video of someone opening folders - so where THIS stretch
    # saw the mark, that is the mark the picture shows.
    out = []
    for i in sorted(take):
        t, h = whole[i]
        if i in mark and mark[i] and row_mark(t) and mark[i] != row_mark(t):
            t = set_mark(t, mark[i])
            h = esc(t)
        out.append((t, h))
    return out


_ELL = re.compile(r"(?<=\S)(?:\.{2,}|\u2026)(?=\S|$)")


def cut_ends(name):
    """A name the screen cut, as (head, tail): Finder cuts in the middle
    ("project_company_...unch_campaign.md"), a narrow tree at the end
    ("project_company_a_launch_c..."). None for a name with no cut."""
    m = _ELL.search(name or "")
    if not m:
        return None
    return name[:m.start()], name[m.end():]


def whole_name_key(name):
    """A cut name as a key, whatever dots the reader gave the cut."""
    return fold(flat(_ELL.sub("...", name or "")))


def unglue_like(whole, head, tail):
    """A whole read glued ("03CompanyB(LandscapeCompany)") spaced the way the
    cut reading spaces its own two ends, and in the middle neither showed,
    the way Finder's names are spaced: before a bracket, and where a small
    letter meets a capital. A reading with no space in it says nothing about
    spacing, and the whole stands as read."""
    if " " not in (head + tail):
        return whole
    nh, nt = len(flat(head)), len(flat(tail))
    i, seen = 0, 0
    while i < len(whole) and seen < nh:
        if whole[i].isalnum():
            seen += 1
        i += 1
    j, seen = len(whole), 0
    while j > 0 and seen < nt:
        j -= 1
        if whole[j].isalnum():
            seen += 1
    if j < i:
        return whole
    mid = whole[i:j]
    mid = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", mid)
    mid = re.sub(r"(?<=[^\s(])(?=\()", " ", mid)
    if head and head[-1:].isalnum() and not head[-1:].isupper() and mid[:1].isupper():
        mid = " " + mid
    if tail and mid and mid[-1:].isalnum() and tail[:1].isupper():
        mid = mid + " "
    if not mid and head and tail and head[-1:].isalnum() and not head[-1:].isupper() and tail[:1].isupper():
        mid = " "
    return re.sub(r"\s{2,}", " ", head + mid + tail).strip()


def unglue_from_cuts(name, cuts):
    """A glued whole, spaced from a cut reading of the same name whose ends
    show the spacing; None where no cut reading fits or the spacing is
    already there."""
    if not re.search(r"[a-z0-9][A-Z]|[^\s(]\(", name):
        return None
    nf = fold(flat(name))
    out = set()
    for c in cuts:
        ends = cut_ends(c)
        if not ends:
            continue
        head, tail = ends
        if " " not in (head + tail):
            continue                    # a reading with no space says nothing
        hf, tf = fold(flat(head)), fold(flat(tail))
        if len(nf) > len(hf) + len(tf) and nf.startswith(hf) and nf.endswith(tf):
            out.add(unglue_like(name, head, tail))
    return out.pop() if len(out) == 1 else None


def complete_name(name, pool, heads):
    """The whole name behind a cut one, or None. First a name read with no
    cut anywhere that opens with the head and closes with the tail (Obsidian
    hides `.md`, so a tree's name may be the Finder name without it); then
    a longer head from a reading cut further along, joined to the tail
    where the two overlap by four letters or more. One answer or none: two
    candidates and the name stays as the screen cut it."""
    c = cut_ends(name)
    if not c:
        return None
    head, tail = c
    hf, tf = fold(flat(head)), fold(flat(tail))
    if len(hf) + len(tf) < 6 or not hf:
        return None
    fits = set()
    for p in pool:
        pf = fold(flat(p))
        for cand, cf in ((p, pf), (p + ".md", pf + "md") if tail.endswith(".md") and not re.search(r"\.\w{1,5}$", p) else (None, None)):
            if cand is None:
                continue
            if len(cf) > len(hf) + len(tf) and cf.startswith(hf) and cf.endswith(tf):
                fits.add(cand)
    # one name however it was spelt: readings that fold to the same letters
    # are one candidate, and the spelling with the most spaces stands
    by_fold = {}
    for cand in fits:
        k = fold(flat(cand))
        if k not in by_fold or cand.count(" ") > by_fold[k].count(" "):
            by_fold[k] = cand
    if len(by_fold) == 1:
        return unglue_like(next(iter(by_fold.values())), head, tail)
    if by_fold or not tail:
        return None
    joined = set()
    for h in heads:
        if len(h) <= len(head) or not fold(flat(h)).startswith(hf):
            continue
        for k in range(min(len(h), len(tail)), 3, -1):
            if h.endswith(tail[:k]):
                joined.add(h + tail[k:])
                break
    return joined.pop() if len(joined) == 1 else None


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


def fold_nameless(table, sni=0):
    """A row read without its name folds into the named row it is: the
    same date, size and kind cell for cell, where it has them. At 00:00:10
    the selected `.claude` row was read as a grey band with no name; the
    stretch kept it as a blank row AND drew `.claude` filled in from the
    other moments, so the list stood one row too long. The band is the
    moment's own and goes with it. Two blank rows alike are one."""
    rows = table.rows
    named = [r for r in rows if sni < len(r["cells"]) and r["cells"][sni]]

    def _fits(r, n):
        if len(n["cells"]) < len(r["cells"]):
            return False
        return any(c for i, c in enumerate(r["cells"]) if i != sni) and all(
            not c or norm(c) == norm(n["cells"][i]) for i, c in enumerate(r["cells"]) if i != sni)
    out, blanks = [], []
    for r in rows:
        if sni < len(r["cells"]) and r["cells"][sni]:
            out.append(r)
            continue
        twin = next((n for n in named if _fits(r, n)), None)
        if twin is not None:
            if r.get("band") and not twin.get("band"):
                twin["band"] = r["band"]
            continue
        if any(_fits(r, b) and _fits(b, r) for b in blanks):
            continue
        blanks.append(r)
        out.append(r)
    table.rows = out


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
        elif st_.path and ft.path:
            # Nothing in this stretch's bar lines up with the window's own.
            # A bar reads from the disk down to the folder shown, so a bar
            # whose LAST crumb is the window's own folder but whose head is
            # not on the window's path was read off something else standing
            # in that row - a sidebar name in the same strip. The window's
            # own bar, read whole elsewhere, is the one that stood there.
            same_end = (fold(flat(st_.path[-1])) == fold(flat(ft.path[-1]))
                        if st_.path and ft.path else False)
            starts = any(name_fits(st_.path[0], c) for c in ft.path)
            if same_end and not starts:
                st_.path = list(ft.path)
    # whatever depth the stretch's bar keeps, each crumb the settled path
    # or the window's title also names is spelt as they spell it: the bar
    # at 00:03:20 kept "Assets" beyond the settled path and so kept its own
    # "(info Product)" too
    if st_.path:
        spelt = {fold(flat(c)): c for c in (ft.path or [])}
        if full.title:
            spelt.setdefault(fold(flat(full.title)), full.title)
        st_.path = [spelt.get(fold(flat(c)), c) if len(flat(c)) >= 6 else c for c in st_.path]
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
    # a name the window knows whole (`_whole_names`), read glued or spaced
    # oddly by this stretch, is spelt as the whole spells it
    wholes = {fold(flat(w)): w for w in (getattr(full, "_whole_names", None) or {}).values()}
    if wholes:
        for r in st_.rows:
            if r["cells"] and r["cells"][0] and not cut_ends(r["cells"][0]):
                w = wholes.get(fold(flat(r["cells"][0])))
                if w and w != r["cells"][0]:
                    r["cells"][0] = w
                    if r["italic"]:
                        r["italic"][0] = False
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
            if not bad and h.startswith("Kind"):
                # a kind read cut (`Folde`) or mangled (`Marko Markd`) where
                # the window's settled row reads a kind: the settled one
                mine_, theirs_ = flat(r["cells"][i]), flat(fr["cells"][j])
                kindish_ = re.compile(r"(folder|document|textfile|json|logfile|application|image|alias)")
                bad = bool(theirs_) and (theirs_.startswith(mine_) and len(mine_) < len(theirs_)
                                         or (not kindish_.search(mine_) and bool(kindish_.search(theirs_))))
            if bad:
                r["cells"][i] = fr["cells"][j]
                if i < len(r["italic"]):
                    r["italic"][i] = False
    # rows the stretch skips between rows it holds. A list is contiguous:
    # where the stretch read row A and row C, and the window's settled list
    # puts B between them, B stood on the screen too and only the reading
    # dropped it. Measured at 00:00:10: `.claude` (the selected row) and
    # `.claude.json` sit between `.CFUserTextEncoding` and
    # `.claude.json.backup`, all four on the frame, and the stretch's reading
    # carried neither. The columns are matched BY HEADING, not by the two
    # tables having identical headers - a stretch that read three of the
    # four columns is still the same list. Nothing is added past the
    # stretch's last row: what follows may be past the fold.
    if len(st_.rows) >= 2:
        def _ni(hdr):
            return next((i for i, h in enumerate(hdr) if h == "Name"), 0)
        fni, sni = _ni(ft.header), _ni(st_.header)
        if os.environ.get("SN_MEND"):
            print("MEND %s hdr=%s full=%s names=%s" % (getattr(sl, "times", "?"), st_.header, ft.header,
                  [r["cells"][sni] if sni < len(r["cells"]) else "" for r in st_.rows]), file=sys.stderr)
        # ONE ROW THE TWO LISTS SPELL DIFFERENTLY DOES NOT STOP THE WALK. The
        # settled list carried `.Jocal` where this stretch read `.local`, and
        # the walk gave up at that row: no row was filled anywhere, and the
        # two rows the stretch had dropped stayed dropped. A row that matches
        # no settled row is kept where it is; the walk goes on from the last
        # row that did match, and only the gaps BETWEEN two matched rows fill.
        def _row_same(a_, b_):
            # the whole name, or the same name with a letter or two read
            # differently - NEVER one name inside another: `.claude` sits
            # inside `.claude.json.backup`, and matching them put the backup
            # in the hovered row's place and drew it twice
            if name_fits(a_, b_):
                return True
            x_, y_ = norm(a_), norm(b_)
            return (len(x_) >= 4 and len(x_) == len(y_)
                    and sum(1 for u, v in zip(x_, y_) if u != v) <= 2)
        idxs, walk = [], 0
        for r in st_.rows:
            name = r["cells"][sni] if sni < len(r["cells"]) else ""
            hit = next((k for k in range(walk, len(ft.rows))
                        if fni < len(ft.rows[k]["cells"]) and name
                        and _row_same(name, ft.rows[k]["cells"][fni])), None)
            idxs.append(hit)
            if hit is not None:
                walk = hit + 1
        ok = sum(1 for k in idxs if k is not None) >= 2
        if ok:
            def _as_mine(fr):
                cells, its = [], []
                for i, h in enumerate(st_.header):
                    j = fni if i == sni else (ft.header.index(h) if h and h in ft.header else None)
                    cells.append(fr["cells"][j] if j is not None and j < len(fr["cells"]) else "")
                    its.append(bool(fr.get("italic") and j is not None and j < len(fr["italic"]) and fr["italic"][j]))
                return {**fr, "cells": cells, "italic": its, "band": None}
            merged, prev = [], None
            for r, k in zip(st_.rows, idxs):
                if k is not None and prev is not None and k > prev + 1:
                    for j in range(prev + 1, k):
                        merged.append(_as_mine(ft.rows[j]))
                merged.append(r)
                if k is not None:
                    prev = k
            st_.rows = merged
        fold_nameless(st_, sni)


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
            box = rect_at(st, ts)[1]
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

    def sel_of(ts):
        """The names selected on this frame: the leftmost banded cell of
        each banded row. A stretch of one screen holds one selection; the
        frames at 00:03:30 and 00:03:40 select two different files and are
        two screens."""
        rows_ = {}
        for p_ in by_ts[ts].get("panes") or []:
            for it in draw2.items_of(p_):
                if it.get("band") and it.get("role") == "cell" and it.get("box"):
                    ky = int(it["box"][1] // 24)
                    if ky not in rows_ or it["box"][0] < rows_[ky][0]:
                        rows_[ky] = (it["box"][0], norm(str(it.get("text") or ""))[:24])
        return {v for _, v in rows_.values() if v}

    def place(st, ts):
        return rect_at(st, ts)[1] or [0, 0, 0, 0]

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
        sel_now = sel_of(ts)
        if same and cur.get("sel") and sel_now and not (cur["sel"] & sel_now):
            same = False
        if same:
            cur["sel"] = sel_now or cur.get("sel") or set()
            cur["t1"] = ts
            cur["ts"].append(ts)
            cur["shows"] = shows or cur["shows"]
            for k, r in rects.items():                # the window's fullest shape over the stretch
                o = cur["rects"][k]
                cur["rects"][k] = [min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3])]
        else:
            if cur:
                spans.append(cur)
            cur = {"t0": ts, "t1": ts, "ts": [ts], "key": key, "rects": rects, "sel": sel_now,
                   "shows": shows, "states": here, "size": by_ts[ts].get("size") or [1920, 1080]}
    if cur:
        spans.append(cur)
    return spans


def bare(w):
    """A bar word without the mark that says one engine only read it."""
    return w[3:-4] if w.startswith("<i>") else w


def doc_rows_as_items(p):
    """A document pane's rows as items, in frame pixels.

    THE MENU BAR CAN LAND IN A DOCUMENT. When the strip along the top of
    the screen is cut into one pane with the note below it, the note
    reader takes the whole pane and the bar becomes the document's first
    line - and a document's rows are not items, so the bar test and the
    bar builder never saw the bar at all while the same words reached the
    picture as loose ink. The rows are measured on the note reader's own
    enlargement of the pane, a whole number of times the pane's width, so
    the enlargement is read off how far the rows reach."""
    d = p.get("data") or {}
    rows = [r for r in (d.get("rows") or []) if r.get("x0") is not None and (r.get("text") or "").strip()]
    if not rows or p.get("kind") != "an open document":
        return []
    ox, oy = p["box"][0], p["box"][1]
    pw = max(1.0, float(p["box"][2] - ox))
    reach = max(float(r["x1"]) for r in rows)
    up = next((s for s in (1.0, 2.0, 3.0, 6.0, 9.0) if reach <= 1.05 * s * pw), 9.0)
    out = []
    for r in rows:
        t = re.sub(r"\s+", " ", str(r.get("text") or "")).strip()
        if not t:
            continue
        out.append({"text": t, "ok": True, "role": "line",
                    "box": [ox + r["x0"] / up, oy + r["y0"] / up, ox + r["x1"] / up, oy + r["y1"] / up]})
    return out


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
            strip = [it for it in draw2.items_of(p) + doc_rows_as_items(p)
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
                if old.CLOCK.match(it["text"]):
                    continue
                # a long reading is a sentence, not a bar - unless it is
                # the whole bar read as one line: several short words, the
                # way one engine reads "File Edit View Go Window Help"
                ws_ = [w for w in re.split(r"\s+", it["text"].strip()) if re.match(r"^[A-Za-z]", w)]
                if len(it["text"]) > 30 and not (len(ws_) >= 3 and all(len(w) <= 12 for w in ws_)):
                    continue
                # two menu names read as one run of letters are two menus --
                # and one engine glues them with a full stop, "File.Edit",
                # which a letters-only test then throws away whole. macOS
                # menu names are each a single word, so a full stop between
                # letters is a join to cut, not part of a name.
                for w in re.split(r"[\s.]+", it["text"].strip()):
                    w = w.strip(" .,:;·|")
                    if not w or not re.match(r"^[A-Za-z][A-Za-z&'-]*$", w):
                        continue
                    if any(same_text(w, bare(x)) for x in here):
                        continue
                    here.append(w if it["ok"] else "<i>" + w + "</i>")
    # The bar and the clock stand until they are read again. A bar is read
    # short as often as it is read whole - a word sits under the cursor, or
    # the strip is cut - so a shorter reading of the SAME bar does not
    # replace the fuller one: the two are put together, the way any part of
    # the screen is filled in from the moment it stood clear. Only a
    # different program at the front, which shows as a different first
    # word, starts the bar over.
    # A WORD CUT SHORT IS MENDED FROM THE SAME BAR READ WHOLE. The bar's
    # first menu sits under the Apple mark and the app's bold name, and
    # one moment reads it as "ile" where another reads "File". A short
    # word that is the tail of a word some other moment read on a bar is
    # that word: the puzzle-piece rule, applied to the bar.
    every = {bare(w) for ws in words_at.values() for w in ws}
    for ts, ws in words_at.items():
        for i, w in enumerate(ws):
            b = bare(w)
            if b in every and len(b) >= 4:
                continue
            full = [k for k in every if k != b and k.endswith(b) and len(b) >= 3
                    and 1 <= len(k) - len(b) <= 2]
            if len(full) == 1:
                ws[i] = full[0] if w == b else "<i>" + full[0] + "</i>"
    # A MENU NAME IS ONE OF A SMALL SET. The bar is set in the smallest type
    # on the screen and `Insert` came back as `inserf` from both engines at
    # one moment. The names a menu bar can carry are few and shared by every
    # program, so a reading a letter or two off one of them is that name --
    # the first of the per-program vocabularies, and the one every program
    # has in common.
    MENU_NAMES = ("File", "Edit", "View", "Go", "Window", "Help", "Insert", "Format",
                  "History", "Bookmarks", "Tools", "Selection", "Run", "Terminal",
                  "Navigate", "Code", "Refactor", "Debug", "Profile", "Tab", "Arrange",
                  "Image", "Layer", "Type", "Select", "Filter", "Share", "Store",
                  "Playback", "Audio", "Modify", "Sequence", "Clip", "Graphics", "Effects")
    for ts_, ws in words_at.items():
        for i, w in enumerate(ws):
            b = bare(w)
            if b in MENU_NAMES or len(b) < 3 or i == 0:
                continue
            near = [n for n in MENU_NAMES
                    if difflib.SequenceMatcher(None, b.lower(), n.lower(), autojunk=False).ratio() >= 0.8]
            if len(near) == 1:
                ws[i] = near[0] if w == b else "<i>" + near[0] + "</i>"
    last_w, last_c = [], ""
    for m in moments:
        got = words_at.get(m["ts"]) or []
        if len(got) >= 3:
            if last_w and same_text(bare(got[0]), bare(last_w[0])):
                merged = list(last_w)
                for w in got:
                    if not any(same_text(bare(w), bare(x)) for x in merged):
                        merged.append(w)
                last_w = merged
            else:
                last_w = got
        words_at[m["ts"]] = last_w
        last_c = clock_at.get(m["ts"], last_c)
        if last_c:
            clock_at[m["ts"]] = last_c
    return words_at, clock_at, strip_at


def drop_crumb_rows(st, crumbs):
    """A row holding one cell that is the tail of a path crumb is the path
    bar, read off a window the screen cut down its left edge
    (`er-Documents-jarvis-demo` for `-Users-jaredrhodenizer-Documents-jarvis-demo`)."""
    tails = [flat(c) for c in crumbs if len(flat(c)) >= 10]
    for q in st.parts:
        if q["fam"] != "table":
            continue
        t = q["model"]
        kept = []
        for r in t.rows:
            cells = r.get("cells") or []
            nm = flat(cells[0]) if cells and cells[0] else ""
            lone = bool(nm) and not any(cells[1:])
            if lone and len(nm) >= 8 and any(c.endswith(nm) and c != nm for c in tails):
                continue
            kept.append(r)
        t.rows = kept


def drop_side_prefix(st):
    """A sidebar name left sitting in front of a file's name.

    A Finder window's sidebar and its list stand side by side inside the
    one window, and where the reader took a row across both, the sidebar's
    word ends up in front of the file: a row reading "Shared .obsidian"
    where the screen showed "Shared" down the side and ".obsidian" in the
    list. The window's own sidebar says which words those are, so they can
    be taken back off - and only those, so a file genuinely named after a
    folder keeps its name.
    """
    for q in st.parts:
        if q["fam"] != "table":
            continue
        t = q["model"]
        side = {fold(flat(w)) for w in (getattr(t, "side", None) or [])
                if len(flat(w)) >= 4}
        if not side:
            continue
        for r in t.rows:
            cells = r.get("cells") or []
            if not cells or not cells[0]:
                continue
            head = cells[0].split()
            for n in (2, 1):
                if len(head) > n and fold(flat(" ".join(head[:n]))) in side:
                    cells[0] = " ".join(head[n:])
                    break


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
        # A NAME IS NOT THE MENU BAR JUST BECAUSE THE APPLICATION IS. `flat`
        # drops the leading dot, so the FOLDER `.obsidian` folds to the same
        # key as the menu bar's own `Obsidian`, and this rule deleted that row
        # from the `vault-demo` list in three pictures. No menu bar and no tab
        # row carries a name beginning with a dot, so a dotted name is never
        # the desk's furniture.
        if text.strip().startswith("."):
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


def label_for(st, at=None):
    """What to call a window in a picture: its program, and what it was
    showing AT THAT MOMENT. A window that opens a different folder later
    must not be named here by the folder it opened later - the picture is of
    this stretch, and the name has to be true of this stretch. Where the
    window was on the screen at a time it says nothing about, the program's
    name stands alone."""
    name = st.name.replace("The ", "").replace(" window", "")
    if at is not None and st.times and not (st.times[0] <= at <= st.times[-1]):
        return name
    return f"{name}: {st.title}" if st.title else name


def behind_for(slice_st, span, subject):
    """Windows that never show in full anywhere, drawn where they sat: the
    strip of a window peeking out above another is the usual case."""
    import furnish
    out = []
    strip = furnish.browser_behind(slice_st)
    if strip:
        rect = rect_at(subject, span["t0"])[1] or [0, 0, 0, 0]
        tops = [t for t in slice_st.topwords]
        if tops:
            W = span["size"][0] if "size" in span else 3840
            H = span["size"][1] if "size" in span else 2160
            # the strip ends where the window in front of it begins: that is
            # all of it that was showing. Its own words must sit above that
            # line, and when they do not they were never part of this strip.
            # A strip reaches as far as its OWN words reach, and no
            # further. The window in front of it may be some other window
            # entirely - the one whose top edge we happen to know is not
            # necessarily the one doing the covering - so the words are the
            # measurement and the front window's top edge is only a cap.
            words_end = max(t[4] for t in tops) + 0.02 * H
            y1 = min(words_end, rect[1]) if rect[1] > 0.01 * H else words_end
            if os.environ.get("UIX_STRIP"):
                print("   strip y1", round(y1), "rect", [round(v) for v in rect],
                      "tops", round(max(t[4] for t in tops)), file=sys.stderr)
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


_MASKED = {}


def masked_share(path):
    """`masked_rows`, remembered - the note asks the same frame twice."""
    if path not in _MASKED:
        try:
            _MASKED[path] = masked_rows(path)
        except Exception:
            _MASKED[path] = 0.0
    return _MASKED[path]


def masked_rows(path):
    """How much of a frame the RECORDING ITSELF blacks out.

    At 00:00:50 of one video two pure-black bands cross the whole screen -
    612 of 2160 rows - and the two Finder windows behind them can never be
    closed, because every edge that would close them is cut. That is the
    source material withholding the pixels, not this tool failing to read
    them, and the difference matters enough to say on the page: everything
    else the note declares is a limit of the reading.

    Checked on the RAW video, the bands are in it - none at 49 seconds, 612
    at 50 and 51 - so this is not the frame builder's doing either.

    A band must be interior: the black above and below a letterboxed video
    is the shape of the picture, not a thing hidden inside it."""
    try:
        from PIL import Image
        import numpy as np
    except Exception:
        return 0.0
    try:
        a = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    except Exception:
        return 0.0
    h, w = a.shape
    if not h or not w:
        return 0.0
    dark = a.mean(axis=1) < 6.0
    hid, run, start = 0, 0, None
    for y in range(h):
        if dark[y]:
            if start is None:
                start = y
        elif start is not None:
            if y - start >= 0.02 * h and start > 0.02 * h and y < 0.98 * h:
                hid += y - start
            start = None
    return hid / float(h)


# A REGION READ AS EMPTY AND A REGION NOT READ ARE DIFFERENT CLAIMS, and the
# bars that tell them apart. Measured by sweeping both over every picture in
# this video: anywhere from 3% to 7% of the frame, and 0.008 to 0.012 ink,
# marks exactly one region and no other -- a broad plateau, so these sit in the
# middle of it rather than on an edge. Below 0.008 the menu-bar strip joins in
# (it is 12.6% of the frame at 0.004 ink, on eight moments); above 0.012
# nothing is marked at all.
GAP_AREA, GAP_INK = 0.05, 0.010
_GAPS = {}


class Gap:
    """A region the reader LOOKED AT and read nothing on, at one moment.

    TEI P5 has separated these since the nineties -- `<gap>`, material left out
    because it could not be read, carrying a REASON and an EXTENT, against
    `<unclear>`, text that WAS read and is doubtful -- and occupancy grids draw
    it again, never letting unobserved collapse into free.

    THE RECORD ALREADY HELD THE GAP. Run 19v said the difference between NOT
    READ and NOT THERE "exists in the record only as prose inside the `text`
    field" and that "there is no structured field for it anywhere". That was
    wrong, and this supersedes it: the reader writes `quiet` -- the panes it
    looked at and could read nothing on -- and states the rule in its own
    words, that refusal is an answer and silence is not. The DRAWING never
    opened it, along with `rendered`, `unwritten`, `standing`, `wins` and
    `lone_panels`: six structured fields written at one end of the pipe and
    read at neither.

    WHAT WAS MISSING IS THE REASON AND THE EXTENT, not the gap. `quiet` holds
    pane indices and nothing else, so "blank wallpaper" and "content I could
    not read" arrive as the same value -- and 65 of this video's 66 quiet
    regions are the first kind. Read as-is it would say nothing useful: the
    unread SHARE does not track picture quality at all (62% on a good picture,
    12% on a bad one). The frame settles it, because the regions can be found
    again and the ink inside them measured."""
    __slots__ = ("ts", "pi", "box", "area", "ink")

    def __init__(self, ts, pi, box, area, ink):
        self.ts, self.pi, self.box, self.area, self.ink = ts, pi, box, area, ink

    @property
    def unread(self):
        """True where something was THERE and did not come back."""
        return self.area >= GAP_AREA and self.ink >= GAP_INK


def gaps_of(m):
    """Every region looked at and not read at this moment, measured.

    No try/except swallowing the answer: a frame that cannot be opened must
    say so, because "nothing was hidden" is a legitimate answer everywhere
    this is read and a silent failure would wear it."""
    ts = m.get("ts")
    if ts in _GAPS:
        return _GAPS[ts]
    quiet = set(m.get("quiet") or [])
    if not quiet:
        _GAPS[ts] = []
        return _GAPS[ts]
    import cv2
    path = frame_of(m)
    img = cv2.imread(path) if path else None
    if img is None:
        raise IOError("cannot open the frame for %s at %r -- the gap for this "
                      "moment cannot be measured, and must not read as none" % (ts, path))
    Hh, Ww = img.shape[:2]
    out = []
    for pi, b in enumerate(panes.frame_regions(img) or []):
        if pi not in quiet:
            continue
        x0, y0, x1, y1 = (int(v) for v in b)
        crop = img[y0:y1, x0:x1]
        ink = (float((cv2.Canny(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), 60, 160) > 0).mean())
               if crop.size else 0.0)
        out.append(Gap(ts, pi, [x0, y0, x1, y1],
                       (x1 - x0) * (y1 - y0) / float(Hh * Ww), ink))
    _GAPS[ts] = out
    return out


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
    # THE BACKDROP HAS A NAME. For the first minutes of a video a window can
    # stand behind others the whole time and never show enough of its own
    # furniture at once to be named: its panes fall into the "rest of the
    # screen" catch-all, and the picture outlines it with a scaffolding
    # label. But its document is the SAME document a named window shows
    # plainly later -- the note read behind two Finders is the note Obsidian
    # opens in full at 04:00 -- so the backdrop takes the name of the window
    # whose text it carries. The bare program name is used, never "The ...
    # window": it must READ as that program in the outline, yet stay a
    # window nobody measured, so it is never pulled up into the filled top
    # layer where the governing rule says only the front window belongs.
    def _doc_fold(st):
        d = st.main_doc()
        if not d or not d.lines:
            return ""
        return fold("".join(flat(t) for t, _ in d.lines))
    _named = [(st, _doc_fold(st)) for st in all_states
              if is_real_window(st.name)]
    _named = [(st, t) for st, t in _named if len(t) >= 40]
    for c in all_states:
        if c.name != "The rest of the screen":
            continue
        ct = _doc_fold(c)
        if len(ct) < 12:
            continue
        for w, wt in _named:
            # autojunk=False is not optional here: on a natural-language
            # string over 200 characters difflib otherwise treats every
            # common letter as junk and the longest run collapses to three
            # or four characters, so the same note read twice fails to match
            # itself. The window's words carry no spaces (the reader glued
            # them), so this is a character run, not a word overlap: a long
            # shared run, or -- for a short fragment -- most of the fragment
            # accounted for, says it is the same document.
            sm = difflib.SequenceMatcher(None, ct, wt, autojunk=False)
            longest = sm.find_longest_match(0, len(ct), 0, len(wt)).size
            frac = sum(b.size for b in sm.get_matching_blocks()) / max(1, len(ct))
            if longest >= 40 or (len(ct) >= 12 and frac >= 0.6):
                c.name = w.name
                c._same_as = w          # the window whose note this is: the cards fold on it
                break
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
        # WHERE the heading sat is evidence about this window at this time,
        # so only readings taken while this state was on the screen count.
        # The same note read at some other moment says nothing about how far
        # this window had been scrolled now.
        for _, b_, t_ in hit:
            if t_ in st.times:
                st.at(t_, make=True).h1 = list(b_)
    real = [st for st in states if is_real_window(st.name)]
    shown = real if real else states          # a video with no named window shows its screens
    import furnish
    furnish.STATES = list(shown)               # so a list can borrow its columns from the same window elsewhere
    windows = []                               # names in order of first appearance
    for st in shown:
        if st.name not in windows:
            windows.append(st.name)
    # The path bars are mended before the windows are told apart, because
    # telling them apart reads the paths. A folder's ancestors are the same
    # tree whichever window shows them, and only what sits between two crumbs
    # a reading already carries is ever filled in, so this cannot move a
    # window into a folder it was never in.
    # A list window's path bar ends at the folder the window is showing.
    # Where the folder's own name was read off the window itself and the
    # bar stops short of it, the bar lost its last crumb to the reading and
    # gets it back. A name the path itself supplied is never added back:
    # that would be the bar arguing with itself.
    for st in states:
        t = st.main_table()
        name = st.title
        if not (t and t.path and name) or getattr(st, "title_from_path", False):
            continue
        t.path = end_at_folder(t.path, name)

    # A crumb the reader cut short - "02 Con" where the folder is called
    # "02 Company A (Info Product)" - is spelt the way the video itself
    # spelt it, but only when exactly one name in the whole video opens
    # that way. Two candidates and the crumb stays as it was read.
    # THE SPELLING THE VIDEO USES MOST. One title read once as "(info
    # Product)" seeded the map ahead of the six rows reading "(Info
    # Product)", and every bar then carried the odd one.
    _spell = {}
    for st in states:
        if st.title:
            _spell.setdefault(flat(st.title), {}).setdefault(st.title, 0)
            _spell[flat(st.title)][st.title] += 1
        for q in st.parts:
            if q["fam"] != "table":
                continue
            for r in q["model"].rows:
                if r["cells"] and r["cells"][0] and "..." not in r["cells"][0]:
                    _spell.setdefault(flat(r["cells"][0]), {}).setdefault(r["cells"][0], 0)
                    _spell[flat(r["cells"][0])][r["cells"][0]] += 1
    known = {k: max(v.items(), key=lambda kv: (kv[1], sum(1 for ch in kv[0] if ch.isupper())))[0]
             for k, v in _spell.items()}
    import furnish
    furnish.KNOWN = dict(known)      # the drawing spells every crumb as the video spells the name most
    times_seen, after = {}, {}
    for st in states:
        t = st.main_table()
        crumbs = list(t.path) if t else []
        for i, c in enumerate(crumbs):
            times_seen[flat(c)] = times_seen.get(flat(c), 0) + 1
            if i:
                after.setdefault(flat(crumbs[i - 1]), set()).add(c)
    for st in states:
        t = st.main_table()
        if not (t and t.path):
            continue
        fixed = []
        for c in t.path:
            f = flat(c)
            # ONE ENGINE GLUES `Users` TO THE FOLDER AFTER IT. `unglue`
            # catches the pair when the next crumb is the glued tail; here
            # the bar read `Macintosh HD > Usersjaredrhodenizer > .claude`
            # with no such next crumb, so the glue stood in two pictures. A
            # crumb that opens with a generic crumb and whose remainder is a
            # name the video knows whole is those two crumbs.
            if f not in known and len(f) >= 10:
                for g_ in ("users", "documents", "desktop", "downloads"):
                    if f.startswith(g_) and f[len(g_):] in known:
                        fixed.append(g_.capitalize())
                        c = known[f[len(g_):]]
                        f = flat(c)
                        break
            # a crumb every other bar also carries is spelt the way the
            # video keeps spelling it; only a crumb read once, and never
            # read as a whole name anywhere, can be a cut-short reading
            if len(f) >= 4 and f not in known and times_seen.get(f, 0) == 1:
                fits = {v for k, v in known.items() if len(k) > len(f) and k.startswith(f)}
                if len(fits) != 1:
                    # a crumb misread mid-word is no prefix of anything. What
                    # names it is the slot: the folders every other bar puts
                    # straight after this same parent, opening the same way
                    par = flat(fixed[-1]) if fixed else None
                    fits = {v for v in after.get(par, ()) if flat(v)[:3] == f[:3]
                            and len(flat(v)) > len(f)}
                if len(fits) == 1:
                    c = fits.pop()
            # a crumb the video knows as a whole name, spelt another way
            # here ("(info Product)"), is spelt as the video knows it
            elif len(f) >= 6 and f in known and c != known[f]:
                c = known[f]
            fixed.append(c)
        t.path = fixed
    # ONLY A BAR ON THE SAME FOLDER, OR ON AN ANCESTOR OF IT, MAY FILL
    # ANOTHER'S GAPS. Mended from every Finder window's bar, a window in
    # `.claude/projects` took crumbs from the window in `vault-demo`, and
    # the bar under the memory window read three folders it never stood
    # in. Ancestors are shared by construction; a sibling folder's bar is
    # another path.
    def _prefix(a, b):
        return len(a) <= len(b) and all(crumb_same(x, y) for x, y in zip(a, b))
    for w in {st.name for st in states}:
        pool = [t for st in states if st.name == w
                for t in [st.main_table()] if t and t.path]
        for t in pool:
            kin = [o.path for o in pool if o is not t
                   and (crumb_same(o.path[-1], t.path[-1]) or _prefix(o.path, t.path) or _prefix(t.path, o.path))]
            t.path = mend_path(t.path, kin)
    # Folder or file, settled once for the whole video. A name whose Kind was
    # read at any moment is that kind at every moment, so a row read without
    # its Kind column borrows the answer rather than guessing at the shape of
    # its name. Nothing is settled that the video never said.
    KIND = re.compile(r"^\s*(Folder|Document|Markdo|JSON|Log File|Alias|App)", re.I)

    def tables_of(st):
        return [q["model"] for q in st.parts if q["fam"] == "table"]

    def row_name_kind(tb, row):
        head = list(tb.header)
        ni = next((i for i, h in enumerate(head) if h == "Name"), 0)
        ki = next((i for i, h in enumerate(head) if h.startswith("Kind")), None)
        cells = list(row.get("cells") or [])
        nm = flat(cells[ni]) if ni < len(cells) else ""
        k = cells[ki] if ki is not None and ki < len(cells) else ""
        if not k:
            k = next((c for c in cells[1:] if KIND.match(str(c or ""))), "")
        return nm, str(k or "")

    kind_of = {}
    for st in states:
        for tb in tables_of(st):
            for row in tb.rows:
                nm, k = row_name_kind(tb, row)
                if nm and KIND.match(k):
                    kind_of.setdefault(nm, k.strip().lower().startswith("folder"))
    for st in states:
        for tb in tables_of(st):
            for row in tb.rows:
                nm, k = row_name_kind(tb, row)
                if not KIND.match(k) and nm in kind_of:
                    row["folder"] = kind_of[nm]

    # A NAME CUT ON SCREEN STANDS WHOLE ON THE CARD IF ANY MOMENT READ IT
    # WHOLE. Finder cuts a long name in the middle and Obsidian's tree cuts
    # the same name at its end, so the head of one reading and the tail of
    # the other are the whole name; a reading with no cut at all is better
    # still. Point 3 of the fourteen, "a card adds up every frame". Only the
    # card changes: a picture keeps the cut the screen made.
    pool, heads, cuts = set(), set(), set()
    for st in all_states:
        for q in st.parts:
            names = []
            if q["fam"] == "table":
                names = [(r.get("cells") or [""])[0] or "" for r in q["model"].rows]
            elif q["fam"] == "tree":
                # a tree line opens with its guide bars and glyphs
                # ("│   name"); only the name is a name
                names = [re.sub(r"^[\s\u2500-\u257f\u203a\u25b8\u25be\u25b9\u2022\-\u00b7>\u02c3\u02c5]+", "", t_ or "") for t_, _h in q["model"].lines]
            for nm in names:
                nm = nm.strip()
                c = cut_ends(nm)
                if c is None:
                    # a name that stops at "_" or "." was clipped by the
                    # pane's edge with no dots to say so
                    # a row or a tree line is a name by construction, spaces
                    # and all ("02 Company A (Info Product)")
                    if len(nm) >= 6 and not nm.endswith(("_", "-", ".", ":")) and len(nm.split()) <= 6:
                        pool.add(nm)
                elif c[0] and not c[1] and len(c[0]) >= 8:
                    heads.add(c[0])
                if c is not None and c[0] and c[1] and " " in (c[0] + c[1]):
                    cuts.add(nm)
    # THE CUT READINGS LIVE IN THE RAW RECORD. A window's gathered rows keep
    # one spelling of each name, and the glued whole won "03 Company B
    # (Landscape Company)"; the cut readings that show its spaces
    # ("03 Company...ape Company)") were folded into it and stood nowhere
    # in any state's rows or trees. They are read off the pieces instead.
    for st in all_states:
        for m_, g_ in (getattr(st, "pieces", None) or ()):
            for p_ in (g_.get("panes") or []):
                if p_.get("kind") not in ("a list of columns", "a file tree"):
                    continue
                for it in draw2.items_of(p_):
                    nm = re.sub(r"\s+", " ", (it.get("text") or "").strip())
                    c = cut_ends(nm)
                    if c and c[0] and c[1] and " " in (c[0] + c[1]) and len(nm) < 60:
                        cuts.add(nm)
    # Recorded on the window, never written into its rows: the rows are
    # what the pictures are cut from, and a whole name there stood beside
    # the stretch's own cut reading as a second row. The card substitutes
    # at drawing time (`furnish.finder`).
    for st in states:
        whole_names = {}
        for tb in tables_of(st):
            for row in tb.rows:
                cells = row.get("cells") or []
                if not cells or not cells[0]:
                    continue
                if not cut_ends(cells[0]):
                    # A NAME READ WHOLE BUT GLUED ("03 CompanyB(LandscapeCompany)")
                    # is spaced the way a cut reading of it spaces its own
                    # two ends; the cut reading is the evidence the spaces
                    # were there
                    whole = unglue_from_cuts(cells[0], cuts)
                    if whole and whole != cells[0]:
                        whole_names[whole_name_key(cells[0])] = whole
                    continue
                whole = complete_name(cells[0], pool, heads)
                if whole and whole != cells[0]:
                    # keyed past the reader's spelling of the cut: the same
                    # name comes back with two dots at one moment and three
                    # at another, and the card draws whichever stood last
                    whole_names[whole_name_key(cells[0])] = whole
        st._whole_names = whole_names
        if os.environ.get("SN_NAMES") and (whole_names or st.name == "The Finder window"):
            print("NAMES %s %s: %s" % (st.name, st.title, whole_names), file=sys.stderr)
    # A TREE LINE SPELT THE WAY THE NAME IS KNOWN. Obsidian's tree carried
    # the same glued spelling ("˃ 03 CompanyB(LandscapeCompany)"), and a
    # tree is drawn on every card of its window.
    all_wholes = {}
    for st in states:
        for w in (getattr(st, "_whole_names", None) or {}).values():
            all_wholes[fold(flat(w))] = w
    if all_wholes:
        for st in all_states:
            for q in st.parts:
                if q["fam"] != "tree":
                    continue
                fixed = []
                for text, html_ in q["model"].lines:
                    nm = re.sub(r"^[\s\u2500-\u257f\u203a\u25b8\u25be\u25b9\u2022\-\u00b7>\u02c3\u02c5]+", "", text or "").strip()
                    w = all_wholes.get(fold(flat(nm))) if nm and not cut_ends(nm) else None
                    if w and w != nm and nm in (text or ""):
                        fixed.append((text.replace(nm, w), (html_ or "").replace(nm, w) if isinstance(html_, str) else html_))
                    else:
                        fixed.append((text, html_))
                q["model"].lines = fixed
    if os.environ.get("SN_NAMES"):
        print("NAMES pool %d cuts %d heads %d" % (len(pool), len(cuts), len(heads)), file=sys.stderr)
        print("NAMES cuts with Company: %s" % sorted(c for c in cuts if "ompany" in c), file=sys.stderr)
        print("NAMES pool with Company: %s" % sorted(c for c in pool if "ompany" in c), file=sys.stderr)
        for st in states:
            for tb in tables_of(st):
                for row in tb.rows:
                    nm = (row.get("cells") or [""])[0] or ""
                    if "ompany" in nm and "03" in nm.replace("O", "0").replace("o", "0"):
                        print("NAMES row %s: %r" % (st.title, nm), file=sys.stderr)

    clocks = [c for m in moments for p in m.get("panes") or [] for c in [old.clock_in(p)] if c]
    parts = [f"# {title}", ""]
    head = f"A screen recording, {old.minutes(secs)} read, {len(moments)} screen moments."
    if windows:
        counts = []
        for w in windows:
            n = sum(1 for st in shown if st.name == w)
            counts.append(f"@@{w}@@" + (f" ({n} states)" if n > 1 else ""))
        head += " On screen: " + "; ".join(counts) + "."
    if clocks:
        head += f" The desktop clock read {clocks[0]}" + (f" at the start and {clocks[-1]} at the end." if clocks[-1] != clocks[0] else ".")
    head += " A word in italics was read by one engine only."
    # WHAT THE RECORDING ITSELF HIDES, said on the page rather than left for
    # the reader to wonder about. This is not a limit of the reading: the
    # video draws black over part of its own screen, and no amount of better
    # reading recovers what was never recorded.
    hidden = []
    for m_ in moments:
        try:
            frac = masked_rows(frame_of(m_))
        except Exception:
            frac = 0.0
        if frac >= 0.05:
            hidden.append((m_["ts"], frac))
    if hidden:
        head += (" The recording itself blacks out part of the screen at "
                 + ", ".join("%s (%.0f%% of the height)" % (t_, 100 * f_) for t_, f_ in hidden)
                 + " - windows behind those bands cannot be drawn, because the video does not carry them.")
    head_at = len(parts)           # filled in once the windows are told apart
    parts += [head, "", "**The order of events**", ""]
    # filled in AFTER the titles are settled: a window whose name was read
    # badly at one moment is spelt from the moment it was read well, and the
    # list at the top must call a window what its own card calls it
    order_at = len(parts)
    parts += [""]
    parts += ["", "---", ""]

    # ------------------------------------------------ the screens, in order
    import furnish
    spans = [s for s in screens(states, moments)
             if any(st in shown for st in s["states"])]

    owner_of = {id(f): frag_owner(f, states) for f in frags}

    # THE PUZZLE-PIECE RULE, APPLIED TO WHAT WAS READ AROUND A WINDOW.
    # A window standing behind others is still read, in whatever pieces the
    # gaps around them leave; those readings were being used to say the
    # window was THERE and never to say what it SAID. So a line the camera
    # covered when the window was in front stayed half a line for good,
    # although a moment when the window stood behind had read it whole.
    # Its own readings belong to its own card: revealed, never invented.
    real_states = [st for st in states if is_real_window(st.name)]
    loose_states = [st for st in states
                    if not is_real_window(st.name) and st.has_content()]
    folding = [(f, owner_of.get(id(f))) for f in frags]
    folding += [(st, frag_owner(st, real_states)) for st in loose_states]
    for f, own in folding:
        if own is None or own == "several" or own is f:
            continue
        for q in f.parts:
            model = q["model"]
            if not hasattr(model, "lines"):
                continue          # a list behind, read in part, is not folded in
            tgt = own.main_doc() if q["fam"] == "doc" else (
                own.tree() if q["fam"] == "tree" else None)
            if tgt is None or tgt is model:
                continue
            tgt.doubt |= getattr(model, "doubt", set())
            tgt.add(list(model.lines))

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

    # The favorites sidebar is one macOS list -- Recents, Shared, Applications,
    # ... -- the same in every Finder window that shows it. One window read it
    # in full; another, standing behind, was re-read only now and then and its
    # sidebar never came home. So the fullest reading of it across the whole
    # video is the house sidebar, carried into a Finder window that PLAINLY
    # showed one but a stretch missed -- told by its own favorites words
    # standing inside its rectangle that stretch, so a window drawn against
    # its own left edge (no room for a sidebar) is never given a false one.
    house_side = max((furnish.side_words_of(st) for st in states
                      if st.name == "The Finder window"), key=len, default=[])
    house_keys = {fold(flat(w)) for w in house_side if len(flat(w)) >= 5}

    def med(vals):
        vals = sorted(vals)
        return vals[len(vals) // 2]

    fit_side = {}      # t0 -> (whole words the fit stood on, its x anchors, its y anchors)

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
        # THREE WORDS READ WHOLE ON BOTH FRAMES, not three numbers: one word
        # gives a width and a height, so two words passed as three votes
        # and 00:04:00 was fitted at 2.18 where its tree rows say 1.76.
        if len(kv) < 3:
            return None
        k = med(kv)
        if not 0.4 <= k <= 4.0:
            return None
        xs = [(p[0], q[0]) for p, q in exact] + [(p[2], q[2]) for p, q in exact]
        xs += [(p[2], q[2]) if side == "tail" else (p[0], q[0]) for p, q, side in cuts]
        ys = [(p[1], q[1]) for p, q in exact] + [(p[1], q[1]) for p, q, _ in cuts]
        if ts_list:
            fit_side[ts_list[0]] = (len(exact), list(xs), list(ys), list(kv))
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

    # TWO WORDS ARE NOT THREE WITNESSES. One matched word gives the fit a
    # width and a height, so two words passed the three-vote test and
    # 00:04:00 was fitted at a zoom of 2.18 where the frame's own tree rows
    # stand 85 px apart against 40.5 at 00:04:10 - a zoom of 1.75. Where the
    # fit stood on fewer than three whole words, the zoom is taken from the
    # tree's row pitch on this frame against a neighbouring moment whose fit
    # stood on enough, and the shift is refitted on the same anchors. The
    # pitch is recorded in the pane image's own pixels, and the reader works
    # a pane at one, two or three times its size, so it is put back to frame
    # pixels by the image's width over the pane's.
    def _png_width(path):
        try:
            with open(path, "rb") as fh:
                fh.read(16)
                return struct.unpack(">I", fh.read(4))[0]
        except Exception:
            return None

    def tree_pitch_at(t):
        m_ = next((mm for mm in moments if mm["ts"] == t), None)
        best = None
        for p_ in (m_ or {}).get("panes") or []:
            d_ = p_.get("data") or {}
            rp = d_.get("row_pitch")
            box = p_.get("box") or []
            if not rp or "tree" not in str(p_.get("kind") or "") or len(box) != 4 or box[2] - box[0] <= 0:
                continue
            w_ = _png_width(machine.here(str(d_.get("source") or "")))
            fac = (w_ / float(box[2] - box[0])) if w_ else 1.0
            val = float(rp) / max(0.5, fac)
            keys_ = {fold(flat(str(l_).strip("\u2502 \u02c3\u02c5\u25b8\u25be")))
                     for l_ in (p_.get("lines") or []) if not str(l_).startswith("[")}
            keys_ = {k_ for k_ in keys_ if len(k_) >= 4}
            if best is None or len(keys_) > len(best[1]):
                best = (val, keys_)
        return best

    for i_, s_ in enumerate(spans):
        T_, side_ = span_T.get(s_["t0"]), fit_side.get(s_["t0"])
        if not T_ or not side_ or side_[0] >= 3:
            continue
        # FOUR VOTES THAT AGREE ARE WITNESSES ENOUGH. Two whole words give
        # four sizes (a width and a height each); where those four stand
        # within 15% of one another the zoom they name is sound, and the
        # row-pitch guess below is what was wrong: at 00:04:00 it read 1.75
        # against the words' 2.1 to 2.3, and the whole desktop was drawn a
        # fifth too large. It stands in only where the words disagree.
        kv_ = side_[3] if len(side_) > 3 else []
        if len(kv_) >= 4 and max(kv_) / max(0.01, min(kv_)) <= 1.15:
            continue
        got_ = tree_pitch_at(s_["t0"])
        if not got_:
            continue
        pitch, keys_here = got_
        ref = None
        # THE SAME TREE, told by its own rows: a Finder's favorites read as
        # a tree at 00:03:50 stand at another pitch altogether
        for j_ in sorted(range(len(spans)), key=lambda j: (abs(j - i_), j)):
            if j_ == i_ or abs(j_ - i_) > 3:
                continue
            Tj, sj = span_T.get(spans[j_]["t0"]), fit_side.get(spans[j_]["t0"])
            if not Tj or not sj or sj[0] < 3:
                continue
            gj = tree_pitch_at(spans[j_]["t0"])
            # ...and the same tree shares most of this frame's rows, not
            # three of them: a Finder list of the same folder names (Assets,
            # Dev, My Product) shared four rows with Obsidian's tree and
            # lent it a Finder's row pitch
            if gj and len(gj[1] & keys_here) >= 3 and len(gj[1] & keys_here) >= 0.4 * len(keys_here):
                ref = (Tj[0], gj[0], spans[j_]["t0"])
                break
        if not ref:
            continue
        k_new = ref[0] * pitch / ref[1]
        if not 0.4 <= k_new <= 4.0:
            continue
        _n, xs_, ys_ = side_[0], side_[1], side_[2]
        dx_ = med([qx - k_new * px for px, qx in xs_]) if xs_ else T_[1]
        dy_ = med([qy - k_new * py for py, qy in ys_]) if ys_ else T_[2]
        if os.environ.get("SN_PITCH"):
            print("PITCH %s: zoom %.2f -> %.2f from tree row pitch %.1f against %.1f at %s (%d whole words)"
                  % (s_["t0"], T_[0], k_new, pitch, ref[1], ref[2], side_[0]), file=sys.stderr)
        span_T[s_["t0"]] = (k_new, dx_, dy_)

    _frame_rects = {}

    _frame_wins = {}

    _frame_big = {}

    def frame_bigwins(s):
        """The windows the SCREEN CUT OFF on this stretch's frame.

        `shapes` closes a window from two sides plus a top and a foot, and
        lets the frame's edge stand in for a missing SIDE but never for a
        missing FOOT -- so a window running off the bottom of the screen is
        never measured, which is why the browser and the Obsidian editor
        were read and never placed. These are measured the other way round,
        from the corner their two drawn edges make."""
        t0 = s["t0"]
        if t0 in _frame_big:
            return _frame_big[t0]
        got = []
        try:
            import bigwin
            m0 = next((mm for mm in moments if mm["ts"] == t0), None)
            path = frame_of(m0) if m0 else None
            if path:
                got = bigwin.big_windows(path)
        except Exception as exc:
            # NEVER SWALLOW THIS SILENTLY. A blanket except here would leave
            # the browser drawn as its chrome strip for ever with nothing
            # anywhere saying why -- which is exactly how the frame-window
            # measurement sat switched off for a whole run.
            sys.stderr.write("frame_bigwins(%s): %s: %s\n"
                             % (t0, type(exc).__name__, exc))
            got = []
        _frame_big[t0] = [[float(v) for v in b] for b in got]
        return _frame_big[t0]

    def browser_chrome(s, bb, foot):
        """The browser's own tabs and address bar, gathered off the FRAME.

        `furnish.browser_behind` reads one window state's top words, and
        the strip's readings are scattered across several panes filed under
        several windows -- so it recovered two tabs of five. The strip is
        not any one window's property: it is a band of the frame, between
        the menu bar's foot and the address row's, inside the browser's own
        box. Gathered that way every tab is there, in the order they sit."""
        got = []
        for t in s["ts"]:
            m_ = next((mm for mm in moments if mm["ts"] == t), None)
            if not m_:
                continue
            for q_ in (m_.get("panes") or []):
                for it in draw2.items_of(q_):
                    b_ = it["box"]
                    cy = (b_[1] + b_[3]) / 2.0
                    if not (bb[1] <= cy <= foot):
                        continue
                    if not (bb[0] - 4 <= b_[0] and b_[2] <= bb[2] + 4):
                        continue
                    got.append((round(cy), b_[0], b_[2], it["text"]))
            if got:
                break
        if not got:
            return []
        got.sort(key=lambda g: (g[0], g[1]))
        # the band holds two rows: the tabs, then the address bar. They are
        # told apart by their own heights, not by a number chosen here.
        ys = sorted({g[0] for g in got})
        cut = ys[0]
        for a_, b2_ in zip(ys, ys[1:]):
            if b2_ - a_ > 0.012 * Hf:
                cut = a_
                break
        else:
            cut = ys[-1]
        tabs, addr, right = [], [], []
        for cy, x0, x1, txt in got:
            if x0 > 0.86 * Wf:
                right.append(txt)
            elif cy <= cut:
                tabs.append((x0, txt))
            else:
                addr.append((x0, txt))
        # ACROSS THE ROW, NOT DOWN IT. The readings in one row differ by a
        # pixel or two in height, so sorting the band by y before x put the
        # third tab first. Within a row the only order is left to right.
        tabs.sort()
        # a piece that begins mid-word is the tail of the tab before it
        joined = []
        for x0, t_ in tabs:
            if joined and (t_[:1].islower() or t_[:1] in "-\u2013\u2014"):
                joined[-1] = (joined[-1][0], joined[-1][1] + t_)
            else:
                joined.append((x0, t_))
        return [(list(bb[:3]) + [foot], joined, [t_ for _, t_ in sorted(addr)], right)]

    def frame_rects(s):
        """The rectangles drawn on this stretch's own frame, near-duplicates
        folded together. These are window edges as the screen drew them, not
        edges worked out from where words sat."""
        return rects_at(s["t0"])

    _frame_imgs = {}

    def _frame_img(path):
        """The frame's own pixels, read once per frame and kept."""
        if path not in _frame_imgs:
            try:
                import cv2
                _frame_imgs[path] = cv2.imread(path)
            except Exception:
                _frame_imgs[path] = None
        return _frame_imgs[path]

    def frame_windows(s):
        """The DISTINCT windows the screen drew on this stretch's frame."""
        t0 = s["t0"]
        if t0 in _frame_wins:
            return _frame_wins[t0]
        m0 = next((mm for mm in moments if mm["ts"] == t0), None)
        got = shapes.windows(frame_of(m0)) if m0 else []
        # A WINDOW IS SOMETHING A PERSON WORKS IN, AND THAT HAS A SIZE - the
        # reader's own law, a tenth of the screen. A smaller rectangle the
        # frame closed is furniture inside a window: a sidebar, a card. One
        # such rectangle, standing over a Finder's sidebar, was drawn as a
        # second window named "Finder" on top of the Finder it was part of.
        # THE WINDOWS THE SCREEN CUTS OFF ARE NOT FOLDED IN HERE, and that
        # is deliberate. `frame_bigwins` is kept a separate list because
        # this one decides several other things -- whether a stretch has any
        # measured window at all, which governs how a maximised front window
        # gets its box -- and adding to it silently changed all of them:
        # measured, 00:04:00 fell 0.34 to 0.17 and two stretches lost their
        # picture entirely. A window `bigwin` measures is used where it is
        # asked for, by name.
        least = 0.09 * Wf * Hf
        kept = [[float(v) for v in r] for r in got
                if (r[2] - r[0]) * (r[3] - r[1]) >= least]
        # ONE WINDOW THE FRAME CLOSED TWICE - once whole, once at its own
        # sidebar divider - is one window. Without this the note drew two
        # `vault-demo` windows at 00:00:10, each with its own traffic lights
        # and title, where the screen had one. The law and the two
        # measurements it rests on live in `panes.fold_split_panes`.
        if len(kept) > 1 and m0:
            im = _frame_img(frame_of(m0))
            if im is not None:
                kept = panes.fold_split_panes(im, kept)
        _frame_wins[t0] = kept
        return _frame_wins[t0]

    SIDE_FLAT = {norm(n) for n in draw2.SIDE_NAMES}

    def sidebar_window(r, t0):
        """A rectangle with a Finder sidebar standing down its own left edge.

        The sidebar's fixed names - Recents, Shared, Applications and the
        rest - are FURNITURE, and furniture belongs to the window it is
        drawn in. The words of a note showing through the gaps around a
        window are not. So a sidebar filling most of a rectangle's width,
        hard against its left edge, says that rectangle is that Finder
        window; the same names inside a much wider rectangle are the Finder
        window standing in front of it, and say nothing about the wider one.
        """
        m0 = next((mm for mm in moments if mm["ts"] == t0), None)
        if not m0:
            return False
        seen = {}
        for p_ in m0.get("panes") or []:
            for it in draw2.items_of(p_):
                b = it.get("box")
                t = norm(it.get("text", ""))
                if not b or t not in SIDE_FLAT:
                    continue
                if (r[0] - 4 <= b[0] and b[2] <= r[2] + 4
                        and r[1] - 4 <= b[1] and b[3] <= r[3] + 4):
                    seen.setdefault(t, (b[0], b[1], b[3]))
        if len(seen) < 4:
            return False
        wide = max(1.0, r[2] - r[0])
        tall = max(1.0, r[3] - r[1])
        lefts = [x for x, _, _ in seen.values()]
        tops = [y for _, y, _ in seen.values()]
        bots = [y for _, _, y in seen.values()]
        # they stand in a COLUMN - one left edge, not scattered across the
        # window - near this rectangle's left edge, and run down a good
        # part of its height. That is a sidebar; anything else is words
        return (max(lefts) - min(lefts) <= 0.15 * wide
                and (min(lefts) - r[0]) <= 0.30 * wide
                and (max(bots) - min(tops)) >= 0.30 * tall)

    def rects_at(t0):
        """The rectangles the screen drew on one moment's frame."""
        if t0 in _frame_rects:
            return _frame_rects[t0]
        m0 = next((mm for mm in moments if mm["ts"] == t0), None)
        got = shapes.find(frame_of(m0)) if m0 else []
        kept = []
        for r in got:
            for k in kept:
                w = min(r[2], k[2]) - max(r[0], k[0])
                h = min(r[3], k[3]) - max(r[1], k[1])
                if w > 0 and h > 0:
                    inter = w * h
                    both = ((r[2] - r[0]) * (r[3] - r[1])
                            + (k[2] - k[0]) * (k[3] - k[1]) - inter)
                    if inter / max(1.0, both) > 0.9:     # the same rectangle
                        break
            else:
                kept.append([float(v) for v in r])
        _frame_rects[t0] = kept
        return kept

    def carry_by_neighbour(st, s):
        """This window's measured box from another moment, carried onto this
        frame by a window that WAS measured at both moments.

        Where a window's own edges were not measured here, its place has to
        come from somewhere. A neighbour measured on both frames gives the
        move between them outright - how much bigger everything got, and
        how far it slid - and that move carries this window across. It is
        two measurements and a ratio, not a guess about where words sat."""
        here = s["t0"]

        def settled(u, t):
            """That window's box at that moment where the SCREEN drew it: its
            own measured edges, or a box that lands on a rectangle the frame
            drew there, which is the same thing said twice."""
            b = u.rects.get(t)
            if not b:
                return None
            if t in getattr(u, "measured", ()):
                return list(b)
            for r in rects_at(t):
                if (furnish._within(b, r) > 0.92
                        and furnish._within(r, b) > 0.92):
                    return list(r)
            return None

        mine = [t for t in getattr(st, "measured", ()) if st.rects.get(t)]
        if not mine or here in mine:
            return None
        secs_here = secs_of.get(here, 0)
        for t in sorted(mine, key=lambda t: abs(secs_of.get(t, 0) - secs_here)):
            there = st.rects[t]
            for u in states:
                if u is st:
                    continue
                a, b = settled(u, t), settled(u, here)
                if not a or not b or a[2] - a[0] <= 0 or a[3] - a[1] <= 0:
                    continue
                kx = (b[2] - b[0]) / (a[2] - a[0])
                ky = (b[3] - b[1]) / (a[3] - a[1])
                if not (0.2 <= kx <= 6.0 and 0.2 <= ky <= 6.0):
                    continue
                if abs(kx - ky) > 0.15 * max(kx, ky):
                    continue        # not one move: the neighbour was resized
                k = (kx + ky) / 2
                return [b[0] + (there[0] - a[0]) * k,
                        b[1] + (there[1] - a[1]) * k,
                        b[0] + (there[2] - a[0]) * k,
                        b[1] + (there[3] - a[1]) * k]
        return None

    def rect_over_panes(st, s):
        """The rectangle the frame drew around the ROWS this window was read
        from at this moment.

        Where a window's own edges were not measured, its place is usually
        worked out from readings carried back and forth across zooms, and
        that arithmetic can run a window clean off the side of the screen.
        But every row read here has a box on this very frame, and a row
        sits inside the window it was read from. So the rectangle holding
        the most of this window's rows IS this window - measured, not
        worked out. Counting rows rather than whole panes matters, because
        the reader often takes a whole side of the screen as one pane and
        two windows can stand in it - so only the rows this window itself
        holds are allowed to vote, told apart by their own words.
        """
        def key_(v):
            if isinstance(v, dict):
                v = (v.get("cells") or [""])[0]
            if isinstance(v, (list, tuple)):
                v = v[0] if v else ""
            return "".join(ch for ch in str(v).lower() if ch.isalnum())

        want = set()
        for t_ in (st.main_table(), ):
            for r_ in (getattr(t_, "rows", None) or []):
                k_ = key_(r_)
                if len(k_) >= 3:
                    want.add(k_)
        # A NOTE WINDOW IS PLACED BY ITS OWN LINES as a list window is by its
        # rows: with no table, Obsidian at 00:04:00 had nothing to vote with
        # and its box was carried in from another zoom, 2.6 times too big.
        for m_ in (st.tree(), st.main_doc()):
            for t_, _h in (getattr(m_, "lines", None) or []):
                k_ = "".join(ch for ch in str(t_).lower() if ch.isalnum())
                if len(k_) >= 6:
                    want.add(k_)
        if not want:
            return None
        spots = []
        for m_, g_ in getattr(st, "pieces", ()):
            if m_["ts"] not in s["ts"]:
                continue
            for p_ in (g_.get("panes") or []):
                pb = p_.get("box")
                d_ = p_.get("data") or {}
                if not pb or len(pb) != 4:
                    continue
                up = float(d_.get("scale") or 0)
                mine_ = []
                for b_ in (d_.get("blocks") or []):
                    rows_ = b_.get("rows") or []
                    boxes_ = b_.get("row_boxes") or []
                    for r_, rb in zip(rows_, boxes_):
                        if (isinstance(rb, (list, tuple)) and len(rb) >= 4
                                and key_(r_) in want):
                            mine_.append(rb)
                if not mine_:
                    continue
                if not up:
                    high = max(1.0, pb[3] - pb[1])
                    all_ = [rb for b_ in (d_.get("blocks") or [])
                            for rb in (b_.get("row_boxes") or [])
                            if isinstance(rb, (list, tuple)) and len(rb) >= 4]
                    up = max(1.0, round(max(rb[3] for rb in all_) / high))
                for rb in mine_:
                    spots.append(((pb[0] + (rb[0] + rb[2]) / 2 / up),
                                  (pb[1] + (rb[1] + rb[3]) / 2 / up)))
        if not spots:
            return None
        best, most = None, 0
        for r in frame_rects(s):
            n = sum(1 for x, y in spots
                    if r[0] <= x <= r[2] and r[1] <= y <= r[3])
            if n > most or (n == most and best is not None and n
                            and (r[2] - r[0]) * (r[3] - r[1])
                            < (best[2] - best[0]) * (best[3] - best[1])):
                best, most = r, n
        # a clear majority, or it says nothing: rows scattered evenly over
        # two rectangles mean the reader took in more than this one window
        if best is None or most < 3 or most < 0.6 * len(spots):
            return None
        return list(best)

    def snap_to_frame(box, s):
        """A box pulled onto the rectangle the frame itself drew there. Only
        a rectangle this box plainly IS - most of each inside the other -
        may claim it; anything looser leaves the box alone, because a wrong
        snap moves a window somewhere it never stood."""
        if not box:
            return box
        area = max(1.0, (box[2] - box[0]) * (box[3] - box[1]))
        fits = []
        for r in frame_rects(s):
            w = min(box[2], r[2]) - max(box[0], r[0])
            h = min(box[3], r[3]) - max(box[1], r[1])
            if w <= 0 or h <= 0:
                continue
            inter = w * h
            ra = max(1.0, (r[2] - r[0]) * (r[3] - r[1]))
            if min(inter / area, inter / ra) >= 0.7:
                fits.append((ra, r, inter / area))
        # The tightest rectangle that holds the whole box. A box worked out
        # from where a window's words sat always sits INSIDE that window, so
        # the window is the smallest measured rectangle that contains it -
        # a pane inside the window would cut a corner off the box, and a
        # bigger rectangle drawn from some other window's edge would swallow
        # ground this window never stood on.
        whole = [(ra, r) for ra, r, cover in fits if cover >= 0.95]
        if whole:
            return list(min(whole)[1])
        return list(max(fits)[1]) if fits else box

    home_reads = {}                # state -> every reading's box, carried home
    secs_of = {m["ts"]: m.get("secs", 0) for m in moments}
    for st in states:
        outs = []
        # Where the reader MEASURED this window's own edges, those moments
        # are the whole story of where it stood: a box worked out from where
        # its words sat is a different shape - taller or wider by whatever
        # the words happened to cover - and averaging the two carries that
        # error into every moment the window has to be drawn from memory.
        only = set(st.measured) & set(st.rects)
        for t, r in st.rects.items():
            if only and t not in only:
                continue
            if not r or r[2] <= r[0]:
                continue
            s_ = next((x for x in spans if t in x["ts"]), None)
            T = (span_T.get(s_["t0"]) if s_ else None) or fit_map([t])
            if not T:
                continue
            # A FRAME THAT IS THE WHOLE SCREEN COMES HOME AS ITSELF. A fit
            # of 0.83 on a full-screen frame (read off a handful of words)
            # carried its windows home a fifth too large, past the screen's
            # edges, and those inflated boxes then stood as candidates for
            # every window's whole. No recording zooms OUT past the desktop,
            # and a frame that shows the desktop bar is the desktop.
            if T[0] < 1.15:
                T = (1.0, 0.0, 0.0)
            outs.append((secs_of.get(t, 0), back(T, r), T[0]))
        if outs:
            home_reads[id(st)] = outs
        if os.environ.get("SN_ZOOM") and st.name == "The Obsidian window":
            print("HOME %s %s: %s" % (st.name, st.times[:1], [(round(o[0]), [round(v) for v in o[1]], round(o[2], 2)) for o in outs]), file=sys.stderr)

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
        # A window standing still is read in pieces, and a piece read on its
        # own looks like a place of its own. Two places that lie one inside
        # the other are one place seen twice, so they are put together; a
        # window that really moved leaves places that do not sit inside each
        # other at all. Without this the same window changed shape from one
        # picture to the next, drawn around whichever corner of it had words.
        merged = True
        while merged and len(clusters) > 1:
            merged = False
            for i in range(len(clusters)):
                for j in range(len(clusters)):
                    if i == j:
                        continue
                    a, b = clusters[i][0], clusters[j][0]
                    small = min((a[2] - a[0]) * (a[3] - a[1]),
                                (b[2] - b[0]) * (b[3] - b[1]))
                    w = min(a[2], b[2]) - max(a[0], b[0])
                    h = min(a[3], b[3]) - max(a[1], b[1])
                    if w > 0 and h > 0 and (w * h) / max(1.0, small) > 0.6:
                        clusters[i][0] = [min(a[0], b[0]), min(a[1], b[1]),
                                          max(a[2], b[2]), max(a[3], b[3])]
                        clusters[i][1].extend(clusters[j][1])
                        clusters.pop(j)
                        merged = True
                        break
                if merged:
                    break
        best = min(clusters, key=lambda c: min(abs(m[0] - want) for m in c[1]))
        # Every reading in the cluster, not the straight-on ones alone. A
        # window does not get smaller because one moment read less of it:
        # the moments are pieces of one window standing still, and the
        # window is as big as the largest piece anyone saw. Taking only the
        # unzoomed readings made the same window change shape from picture
        # to picture, and shrank it to whichever corner had words in it.
        take = best[1]
        return [min(m[1][0] for m in take), min(m[1][1] for m in take),
                max(m[1][2] for m in take), max(m[1][3] for m in take)]

    def hold_panes(box, st_, times, Wf_):
        """The same box, widened sideways to hold the panes this window was
        read from at these moments. A pane wider than half the frame is a
        slab the reader took in whole, covering more than one window, and
        it says nothing about where this one stood."""
        if not box:
            return box
        lo_x, hi_x = box[0], box[2]
        for m_, g_ in getattr(st_, "pieces", ()):
            if m_["ts"] not in times:
                continue
            for p_ in (g_.get("panes") or []):
                b_ = p_.get("box")
                if not b_ or b_[2] - b_[0] > 0.5 * Wf_:
                    continue
                lo_x, hi_x = min(lo_x, b_[0]), max(hi_x, b_[2])
        if hi_x - lo_x > Wf_:
            return list(box)
        return [lo_x, box[1], hi_x, box[3]]

    def title_from_bar(states):
        """A Finder window with no title takes the folder its own path bar
        ends at. The bar reads from the disk down to what is showing, and
        where its last crumb is a row of the list it is the SELECTED item,
        not the folder - the folder is the crumb before it."""
        for st_ in states:
            if st_.title or st_.name != "The Finder window":
                continue
            t_ = st_.main_table()
            path = list(getattr(t_, "path", None) or [])
            if len(path) < 2:
                continue
            rows = {fold(flat((r.get("cells") or [""])[0])) for r in t_.rows
                    if (r.get("cells") or [""])[0]}
            last = path[-1]
            if len(path) >= 2 and (fold(flat(last)) in rows
                                   or any(same_text(last, r) for r in rows)):
                last = path[-2]
            if last and len(flat(last)) >= 2:
                st_.title = last

    def heal_titles(states):
        """A window's title read badly at one moment, spelt from the moment
        it was read well.

        The title bar is the same pixels every moment; what differs is how
        much of it the frame gave up. "vautt-demo" and "02Con" are the same
        two folders as "vault-demo" and "02 Company A (Info Product)" -
        one a letter mistaken, one a name cut short - and the picture
        should call a folder by its name, not by the worst reading of it.
        Only a title ANOTHER moment actually read may stand in; nothing is
        spelt out that was never on the screen.
        """
        import difflib
        titles = [st_.title for st_ in states if st_.title]
        if len(titles) < 2:
            return
        seen = {}
        for t_ in titles:
            seen[t_] = seen.get(t_, 0) + 1
        # a title that also stands in some window's path bar was read whole
        crumbs = set()
        for st_ in states:
            t_ = st_.main_table()
            for c in (getattr(t_, "path", None) or []):
                crumbs.add(fold(flat(c)))

        def rank(t_):
            return (fold(flat(t_)) in crumbs, seen[t_], len(t_))

        for st_ in states:
            mine = st_.title
            if not mine:
                continue
            fm = fold(flat(mine))
            best = mine
            for other in seen:
                if other == mine:
                    continue
                fo = fold(flat(other))
                near = (len(fm) >= 4 and len(fo) > len(fm)
                        and difflib.SequenceMatcher(
                            None, fm, fo[:len(fm)]).ratio() >= 0.8)
                like = (len(fm) >= 6 and abs(len(fo) - len(fm)) <= 2
                        and difflib.SequenceMatcher(None, fm, fo).ratio() >= 0.85)
                if (near or like) and rank(other) > rank(best):
                    best = other
            if best != mine:
                st_.title = best

    def words_in(box, st_, times):
        """How many of this window's OWN words were read inside that box."""
        keys = own_words.get(id(st_)) or set()
        if not keys:
            return 0
        n = 0
        for t in times:
            for key, b in (words_of.get(t) or {}).items():
                if not ((len(key) >= 5 and key in keys)
                        or (len(key) >= 6 and any(key in sk for sk in keys))
                        or (len(key) >= 12 and any(sk in key for sk in keys))):
                    continue
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
                    n += 1
        return n

    def hold_words(box, st_, times, Wf_, Hf_):
        """The same box, widened to hold the words this window's own reading
        carries, where the reader found them at these moments.

        A window holds its own words - that is what a window is. A box
        worked out from readings carried across zooms can come out beside
        them or inside them, and then the picture shows words standing on
        bare desktop with the window they belong to drawn somewhere else.
        A window behind is read in fragments, the windows in front cutting
        its lines up, so a run of six letters sitting inside one of its own
        lines counts.
        """
        if not box:
            return box
        keys = own_words.get(id(st_)) or set()
        if not keys:
            return box
        out = list(box)
        for t in times:
            for key, b in (words_of.get(t) or {}).items():
                if not ((len(key) >= 5 and key in keys)
                        or (len(key) >= 6 and any(key in sk for sk in keys))
                        or (len(key) >= 12 and any(sk in key for sk in keys))):
                    continue
                out = [min(out[0], b[0]), min(out[1], b[1]),
                       max(out[2], b[2]), max(out[3], b[3])]
        # A window's own words place it; words that would DOUBLE it are
        # not its own. Two windows showing the same folder names read
        # alike, and a box stretched over both says one window stood where
        # two did.
        wide0 = max(1.0, box[2] - box[0])
        tall0 = max(1.0, box[3] - box[1])
        if (out[2] - out[0]) > 2.0 * wide0 or (out[3] - out[1]) > 2.0 * tall0:
            return list(box)
        return out

    list_not_tree(states)
    _all_crumbs = [c for st in states for q in st.parts if q["fam"] == "table"
                   for c in (q["model"].path or [])]
    for st in states:
        sidebar_from_panes(st, house_side)
        tidy_side(st.main_table(), house_side, st.title)
        drop_crumb_rows(st, _all_crumbs)
    house_side = max((furnish.side_words_of(st) for st in states
                      if st.name == "The Finder window"), key=len, default=house_side)
    house_keys = {fold(flat(w)) for w in house_side if len(flat(w)) >= 5}
    # the house sidebar's share of its window, for a Finder drawn with the
    # house's favorites but never measured with them: the median of the
    # windows that were
    _hs = sorted(v for v in (furnish.side_share_card(st) for st in states
                             if st.name == "The Finder window") if v)
    house_share = _hs[len(_hs) // 2] if _hs else None
    mend_prose(all_states)
    # A NOTE'S LINE IS SPELT BY THE VOTE OF ITS READINGS. Every moment reads
    # the open note again, and the readings of one line differ by a letter
    # here and there: "02 Company A/ : the first business" was read ten
    # times with the 0 (glued) and eight times with a 6 (spaced), and the
    # spaced reading stood, 6 and all, because the merge prefers words to
    # glue. The letters are the majority's; the spacing stays the drawn
    # line's own. Only a pure substitution is taken (the same letters
    # count), so a fragment or a re-wrapped reading changes nothing.
    for st in all_states:
        raw = []
        for m_, g_ in (getattr(st, "pieces", None) or ()):
            for p_ in (g_.get("panes") or []):
                if p_.get("kind") == "an open document":
                    raw.extend(x for x in (p_.get("lines") or []) if isinstance(x, str) and len(x) >= 12)
        if not raw:
            continue
        for q in st.parts:
            if q["fam"] != "doc" or not getattr(q["model"], "lines", None):
                continue
            fixed = []
            for t_, h_ in q["model"].lines:
                pl = plain_line(t_)
                if len(pl) < 12:
                    fixed.append((t_, h_))
                    continue
                tally = {}
                for r_ in raw:
                    if same_doc_line(r_, t_):
                        k_ = plain_line(r_)
                        tally[k_] = tally.get(k_, 0) + 1
                if not tally:
                    fixed.append((t_, h_))
                    continue
                win = max(tally.items(), key=lambda kv: (kv[1], kv[0] == pl))[0]
                if win == pl or len(win) != len(pl) or tally[win] <= tally.get(pl, 0):
                    fixed.append((t_, h_))
                    continue
                # the drawn line's letters replaced in place, its spacing kept
                out, k = [], 0
                for ch in t_:
                    if ch.isalnum():
                        out.append(win[k] if ch.islower() or ch.isdigit() else win[k].upper())
                        k += 1
                    else:
                        out.append(ch)
                t2 = "".join(out)
                if plain_line(t2) != win:
                    fixed.append((t_, h_))
                    continue
                # the html carries the same letters somewhere; swap the
                # differing stretch, and only where it stands once
                i0 = 0
                while i0 < min(len(t_), len(t2)) and t_[i0] == t2[i0]:
                    i0 += 1
                j0 = 0
                while j0 < min(len(t_), len(t2)) - i0 and t_[-1 - j0] == t2[-1 - j0]:
                    j0 += 1
                a_, b_ = t_[i0:len(t_) - j0], t2[i0:len(t2) - j0]
                # widen to whole words so the swap is unambiguous in the html
                while i0 > 0 and t_[i0 - 1].isalnum():
                    i0 -= 1
                while j0 > 0 and t_[len(t_) - j0].isalnum():
                    j0 -= 1
                a_, b_ = t_[i0:len(t_) - j0], t2[i0:len(t2) - j0]
                ea, eb = esc(a_), esc(b_)
                h2 = h_.replace(ea, eb) if isinstance(h_, str) and h_.count(ea) == 1 else h_
                if os.environ.get("SN_NAMES"):
                    print("DOC %s: %r -> %r (%d vs %d)" % (st.name, a_, b_, tally[win], tally.get(pl, 0)), file=sys.stderr)
                fixed.append((t2, h2))
            q["model"].lines = fixed
    title_from_bar(states)
    heal_titles(states)
    flatten_sidebars(all_states)
    parts[order_at] = "\n".join(
        f"- {span_of(st)} - {st.name[0].lower() + st.name[1:]}"
        + (f": {st.title}" if st.title else "") for st in shown)
    own_words = {id(st): {flat(w) for w in box_texts(st)[1] if len(flat(w)) >= 8}
                 for st in states}
    bar_seen = set()               # moments whose own top strip held readings
    for m in moments:
        n = 0
        for p in m.get("panes") or []:
            if p["box"][1] > 0.02 * Hf:
                continue
            for it in draw2.items_of(p) + doc_rows_as_items(p):
                if it["box"][1] <= 0.01 * Hf and it["box"][3] <= 0.03 * Hf and len(it["text"]) >= 3:
                    # THE BAR IS COUNTED IN WORDS, NOT READINGS. One engine
                    # reads the whole menu bar as a single line - "File Edit
                    # View Go Window Help" - and counted as one reading it
                    # fell under the two this asks for, so the first picture
                    # of the video was drawn with no bar and the bar's own
                    # words floating loose across the top.
                    n += len([w for w in it["text"].split() if len(w) >= 2])
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


    # How wide the note's own text ran inside its pane. A note is set to a
    # readable line length, not to the width of the window, so a drawn note
    # spread over the whole pane does not look like the note in the video.
    # The measure is the words' own span against the pane they sat in.
    for st in states:
        wide, at = [], {}
        for m, g in getattr(st, "pieces", ()):
            docs = [q for q in (g.get("panes") or []) if q.get("kind") == "an open document"]
            if not docs:
                continue
            p_ = max(docs, key=lambda q: q["box"][2] - q["box"][0])
            pw = p_["box"][2] - p_["box"][0]
            xs = [it["box"] for it in draw2.items_of(p_) if it["box"][2] - it["box"][0] > 20]
            if pw > 0 and len(xs) >= 3:
                span = max(b[2] for b in xs) - min(b[0] for b in xs)
                if 0.2 <= span / pw <= 1.0:
                    wide.append(span / pw)
                    at[m["ts"]] = span / pw
                    st.at(m["ts"], make=True).doc_wide = span / pw
        if wide:
            st._doc_wide = round(100 * med(sorted(wide)))

    # A NOTE'S LINE LENGTH BELONGS TO THE PROGRAM, NOT TO ONE READING OF IT.
    # A note is set to a readable line length and that does not change from
    # moment to moment; what changes is whether this stretch happened to
    # read enough of the pane to measure it. Where a stretch measured none,
    # the same window's own measurement from a moment that DID is the honest
    # width -- the puzzle-piece rule the note already sanctions for a fill,
    # applied to the shape of the text instead of to its words. Without it
    # the backdrop Obsidian at 00:00:00 had no width at all and its note was
    # drawn across the whole pane, where the screen ran it in a column about
    # half that: lines landing where the frame has none.
    _wide_home = {}
    for st in states:
        w_ = getattr(st, "_doc_wide", 0)
        if w_:
            _wide_home.setdefault(st.name, []).append(w_)
    _wide_home = {k: round(med(sorted(v))) for k, v in _wide_home.items()}
    for st in states:
        if not getattr(st, "_doc_wide", 0) and _wide_home.get(st.name):
            st._doc_wide = _wide_home[st.name]
            st._doc_wide_borrowed = True

    for st in states:
        for t_, b_ in [(t, sn.h1) for t, sn in st.moments() if sn.h1]:
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

    # How far apart each program sets one row from the next, at the base
    # zoom. One window of a program is measured badly now and then - a pane
    # comes out a sliver, or is missed - but the program's rows are the same
    # height everywhere, so every window of it votes and the vote stands for
    # all of them. Without this the same list is drawn at three sizes in
    # three pictures of the same screen.
    def pitch_of_pane(p_):
        d_ = p_.get("data") or {}
        tops = []
        for b_ in (d_.get("blocks") or []):
            tops += [rb[1] for rb in (b_.get("row_boxes") or [])
                     if isinstance(rb, (list, tuple)) and len(rb) >= 4]
        for key in ("rows", "body_rows"):
            tops += [x["y0"] for x in (d_.get(key) or [])
                     if isinstance(x, dict) and "y0" in x]
        tops = sorted(set(tops))
        if len(tops) < 4:
            return None
        gaps = [b - a for a, b in zip(tops, tops[1:]) if 0 < b - a < 1200]
        if len(gaps) < 3:
            return None
        best = max(gaps, key=lambda g: sum(1 for h in gaps if abs(h - g) <= 0.15 * g))
        like = [h for h in gaps if abs(h - best) <= 0.15 * best]
        if len(like) < 3:
            return None
        high = p_["box"][3] - p_["box"][1]
        up = float(d_.get("scale") or 0)
        if not up and high > 0:
            up = max(1.0, round(max(tops) / high))
        return (len(tops), (sum(like) / len(like)) / max(1.0, up))

    # How tall one row stands, held as a FRACTION of the window's own
    # width. Both are measured on the same frame, so the zoom cancels: a
    # window filmed close up has taller rows AND a wider box, in step. A
    # window running off the side of the frame has no true width, so it
    # never votes - its box is cut by the frame, not by the window.
    pitch_home, every = {}, []
    tall_home, tall_every = {}, []
    for st_ in states:
        seen_, high_ = [], []
        for m_, g_ in getattr(st_, "pieces", ()):
            rc_ = st_.rects.get(m_["ts"])
            if not rc_ or rc_[2] - rc_[0] <= 0 or rc_[3] - rc_[1] <= 0:
                continue
            Wm_, Hm_ = (m_.get("size") or [3840, 2160])[:2]
            best_ = None
            for p_ in g_.get("panes") or []:
                got_ = pitch_of_pane(p_)
                if got_ and (best_ is None or got_[0] > best_[0]):
                    best_ = got_
            if not best_:
                continue
            if rc_[0] >= 1 and rc_[2] <= Wm_ - 1:
                seen_.append(best_[1] / (rc_[2] - rc_[0]))
            if rc_[1] >= 1 and rc_[3] <= Hm_ - 1:
                high_.append(best_[1] / (rc_[3] - rc_[1]))
        if seen_:
            pitch_home.setdefault(st_.name, []).extend(seen_)
            every.extend(seen_)
        if high_:
            tall_home.setdefault(st_.name, []).extend(high_)
            tall_every.extend(high_)
    pitch_home = {k: med(sorted(v)) for k, v in pitch_home.items()}
    if every:
        pitch_home["*"] = med(sorted(every))
    tall_home = {k: med(sorted(v)) for k, v in tall_home.items()}
    if tall_every:
        tall_home["*"] = med(sorted(tall_every))

    _zoom = {}

    def _here(path):
        """A path written by the Windows side, read from this one."""
        if len(path) > 2 and path[1] == ":":
            return "/mnt/" + path[0].lower() + path[2:].replace("\\", "/")
        return path

    def pane_zooms(p_):
        """The two zooms a pane's record can be written in.

        A pane is cut from the frame and written enlarged, and the loose
        readings are made on THAT picture - so its own width over the
        pane's width is their zoom, and it is on disk to be measured. A
        document's rows are not: the note reader enlarges again for itself
        and answers in its own pixels, which is why one note's writing came
        out three times its size. Nothing there is written down, but a row
        cannot reach past the picture it was read from, and a zoom is a
        whole number - so the rows' own reach gives it.
        """
        key = id(p_)
        if key in _zoom:
            return _zoom[key]
        d_ = p_.get("data") or {}
        wide = max(1, p_["box"][2] - p_["box"][0])
        high = max(1, p_["box"][3] - p_["box"][1])
        shot = 0.0
        pic = p_.get("image")
        if pic:
            try:
                from PIL import Image as _Im
                with _Im.open(_here(pic)) as im_:
                    shot = im_.size[0] / float(wide)
            except Exception:
                shot = 0.0
        if shot < 0.9:
            shot = float(d_.get("scale") or 1) or 1.0
        # A document's rows are measured on the note reader's own THREE
        # TIMES enlargement of that same picture (note_reader enlarges by 3
        # before it measures a stroke), so their zoom is the picture's own
        # times three. Checked against the fixtures: on a pane written at
        # one, the rows reach 2772 of 1381 x 3; on a pane written at two,
        # 3089 of 672 x 6. Neither ever reaches past its own picture.
        rows_up = shot * 3.0
        _zoom[key] = (float(shot), float(max(1.0, rows_up)))
        return _zoom[key]

    def screen_ink(s, taken):
        """Every reading no filled window claims, back at its own place.

        The screen is not only its windows: a browser filling it, a note
        standing behind everything, the bar across the top. Those were read
        and then dropped, because the picture drew what stood inside a
        measured rectangle and nothing else.
        """
        m0 = next((mm for mm in moments if mm["ts"] == s["t0"]), None)
        if not m0:
            return []
        W_, H_ = (m0.get("size") or [1920, 1080])[:2]
        barred_ = s["t0"] in bar_seen
        out = []
        for p_ in (m0.get("panes") or []):
            bx = p_.get("box")
            if not bx:
                continue
            shot_up, rows_up = pane_zooms(p_)
            d_ = p_.get("data") or {}
            said = []
            reads = [(r_.get("box"), (r_.get("text") or "").strip())
                     for r_ in (d_.get("readings") or [])]
            reads = [(b_, t_) for b_, t_ in reads if b_ and t_]
            # ONE PANE, ONE SIZE OF TYPE. A reading's box is the engine's
            # guess at where the letters stop, and it wanders by a third
            # from one line to the next of the same paragraph, so sized
            # line by line the same body text stood in four sizes on one
            # picture. The pane's writing has one size - the middle of its
            # readings - and only a line far taller than that (a heading)
            # keeps its own. And the box is not the type: an engine's box
            # stands a little taller than the letters, and dividing it by
            # the ink's share of an em on top drew every word two fifths
            # too big. Measured on the frame: a 40-pixel box holds type
            # that a 38-pixel font-size draws.
            highs = sorted(float(b_[3] - b_[1]) for b_, _t in reads)
            med_ = highs[len(highs) // 2] if highs else 0.0
            for b_, t_ in reads:
                own_h = float(b_[3] - b_[1])
                if med_ and 0.6 * med_ <= own_h <= 1.5 * med_:
                    own_h = med_
                said.append((b_, t_, own_h * 0.95 * 0.72, shot_up))
            line = float(d_.get("body_height") or 0)
            # the same one-size rule for a document's rows: the em each
            # block's shape gives is noisy - a wrapped paragraph and a
            # one-line row of the same type come out a third apart - so
            # the body rows of one pane take the middle of their ems and
            # only a row far larger (a heading) keeps its own
            rows_em = []
            for row in (d_.get("rows") or []):
                t_ = (row.get("text") or "").strip()
                if not t_ or row.get("x0") is None:
                    continue
                wide_ = max(1.0, (row["x1"] - row["x0"]) / rows_up)
                deep_ = max(1.0, (row["y1"] - row["y0"]) / rows_up)
                rows_em.append(math.sqrt(wide_ * deep_ / (0.7 * max(1, len(t_)))))
            body_em = sorted(rows_em)[len(rows_em) // 2] if rows_em else 0.0
            for row in (d_.get("rows") or []):
                t_ = (row.get("text") or "").strip()
                if not t_ or row.get("x0") is None:
                    continue
                # A ROW OF A DOCUMENT IS A BLOCK OF LINES, NOT ONE LINE. Its
                # box is as tall as the paragraph, and sizing the type by
                # that drew a sentence across half the screen. The pane's
                # own measured line height is the size of its writing.
                high = row["y1"] - row["y0"]
                # THE BLOCK'S OWN SHAPE SAYS WHAT SIZE IT IS SET IN. The
                # measured line height cannot be trusted here: it reaches
                # the record through two different reader paths, in one of
                # which it is measured on a threefold enlargement and in
                # the other on the pane itself, and the same figure then
                # draws one note's writing at a third of its size and
                # another's at three times. A block of text has an area and
                # a number of characters, and only one type size fills it:
                # a line of type is about one and two fifths of its own em
                # tall, and its letters about half an em wide.
                wide_ = max(1.0, (row["x1"] - row["x0"]) / rows_up)
                deep_ = max(1.0, (row["y1"] - row["y0"]) / rows_up)
                chars = max(1, len(t_))
                em = math.sqrt(wide_ * deep_ / (0.7 * chars))
                if body_em and 0.6 * body_em <= em <= 1.5 * body_em:
                    em = body_em
                said.append(([row["x0"], row["y0"], row["x1"], row["y1"]],
                             t_, em * 0.72 * rows_up, rows_up))
            for b_, t_, high, up in said:
                x0 = bx[0] + b_[0] / up
                y0 = bx[1] + b_[1] / up
                x1 = bx[0] + b_[2] / up
                y1 = bx[1] + b_[3] / up
                mid = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
                if any(r[0] <= mid[0] <= r[2] and r[1] <= mid[1] <= r[3]
                       for r in taken):
                    continue          # this window draws it properly itself
                if x1 <= x0 or y1 <= y0:
                    continue
                # THE BAR IS DRAWN ONCE. Where the picture draws the desktop
                # bar, the bar's own readings - its menus and the clock -
                # are not laid down again as loose words on top of it,
                # which printed every menu twice at two sizes.
                if barred_ and y1 <= 0.035 * H_:
                    continue
                # A SCRAP AGAINST A WINDOW'S EDGE IS THE CUT END OF A WORD,
                # not a word: "Va" and "es" beside a Finder are what the
                # Finder left of "Vault" and "Properties". The word stands
                # behind the window and the window covers the rest of it;
                # the scrap on its own says nothing true.
                if len(re.sub(r"[^A-Za-z0-9]", "", t_)) < 3 and any(
                        abs(x0 - r[2]) <= 0.015 * W_ or abs(x1 - r[0]) <= 0.015 * W_
                        for r in taken):
                    continue
                tall_ = float(high) / up
                # nothing on a screen is written a twentieth of the screen
                # tall; a figure that says so is a block measured as a line
                if tall_ < 1 or tall_ > 0.05 * H_:
                    continue
                out.append((x0, y0, x1, y0 + tall_, t_))
        return out

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
                  "Each picture is the shape of the screen over that stretch of time: the desktop bar with its own "
                  "words along the top wherever the bar was read, and every window standing where it stood, at the "
                  "size it was. The window the "
                  "stretch is about is filled in with what it really said, at type that reads, cut off by the edges of "
                  "the box it stood in; every window behind it is a named outline, because only the front one was "
                  "fully in view. No photograph is ever pasted in -- where the camera covered the screen, that corner "
                  "is outlined and said. Each window is drawn again below, on its own and whole. A stretch covers "
                  "several timestamps whenever the screen stood still, and the stamp in the corner says which; where "
                  "the reader measured a window's edges those are the edges drawn, otherwise they are taken from "
                  "where that window's own words sat.", ""]
        last_T = None
        at_idx = {m["ts"]: i for i, m in enumerate(moments)}

        def _agree(a, b):
            return all(abs(a[i] - b[i]) <= (0.04 * Wf if i % 2 == 0 else 0.04 * Hf) for i in range(4))

        _all_words = {}

        def all_words_of(t):
            """Every reading on that moment's panes, as (key, box) - a size
            or a kind read on sixteen rows is sixteen readings, and a window
            showing only sizes and kinds is placed by them."""
            if t not in _all_words:
                m_ = next((mm for mm in moments if mm["ts"] == t), None)
                got = []
                for p_ in (m_ or {}).get("panes") or []:
                    for it in draw2.items_of(p_):
                        key = fold(flat(it["text"]))
                        if len(key) >= 5:
                            got.append((key, it["box"]))
                _all_words[t] = got
            return _all_words[t]

        def any_words_in(box, st_, times):
            """How many of this window's own words - any of them, the
            sidebar's fixed names and the sizes in its list included - were
            read inside that box at these moments."""
            keys = {fold(flat(w)) for w in state_texts(st_) if len(flat(w)) >= 5}
            n = 0
            for t in times:
                for key, b in all_words_of(t):
                    if not (key in keys or (len(key) >= 6 and any(key in sk for sk in keys))):
                        continue
                    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                    if box[0] <= cx <= box[2] and box[1] <= cy <= box[3]:
                        n += 1
            return n

        def measured_rects_at(t):
            return [st_.rects[t] for st_ in states if t in st_.measured and st_.rects.get(t)]

        def still_here(own, s_, base_, extra_):
            """The place a window stood at this stretch, where the frames
            either side measured it in the same place and its own words are
            read inside that place now - the window stood still and the
            reader merely failed to close it here. Returns (box, the moment
            to draw it from) or None.

            At 00:00:50 the video's black bands cut every edge of the
            vault-demo Finder, so no rectangle closed and the picture showed
            one window where the screen held three. The same window was
            measured at 00:00:30 and at 00:01:00 at the same place, the
            Finder beside it stands where it stood, and its favorites are
            read inside its box at 00:00:50. Tristan's puzzle-piece rule
            fills what was hidden from a moment it stood clear."""
            why = os.environ.get("SN_STILL") == "2"
            meas = sorted(t for t in own.measured if own.rects.get(t))
            if not meas:
                return None
            i0, i1 = at_idx.get(s_["t0"], 0), at_idx.get(s_["t1"], 0)
            before = [t for t in meas if t < s_["t0"] and i0 - at_idx.get(t, -99) <= 5]
            after = [t for t in meas if t > s_["t1"] and at_idx.get(t, 99) - i1 <= 5]
            tb, ta = (before[-1] if before else None), (after[0] if after else None)
            if tb is None and ta is None:
                if why:
                    print("STILL? %s %s: no measured neighbour (meas %s; i0 %s i1 %s idx %s)"
                          % (s_["t0"], label_for(own), meas, i0, i1, [at_idx.get(t) for t in meas]), file=sys.stderr)
                return None
            rb, ra = (own.rects[tb] if tb else None), (own.rects[ta] if ta else None)
            if rb and ra and not _agree(rb, ra):
                if why:
                    print("STILL? %s %s: moved %s -> %s" % (s_["t0"], label_for(own), rb, ra), file=sys.stderr)
                return None
            box = [(x + y) / 2 for x, y in zip(rb, ra)] if (rb and ra) else list(rb or ra)
            anchor = tb if tb else ta
            # the same zoom: some other window measured on both frames, at
            # the same place on both - the screen did not move between them
            # ANY window measured on both frames at the same place will do:
            # the Finder beside it is a different state at 00:00:30 (folder
            # `jaredrhodenizer`) and at 00:00:50 (folder `.claude`), and it
            # is the same rectangle on both frames
            zoom_ok = any(_agree(r1, r2)
                          for r1 in measured_rects_at(anchor)
                          for r2 in measured_rects_at(s_["t0"]))
            if not zoom_ok:
                if why:
                    print("STILL? %s %s: zoom changed since %s" % (s_["t0"], label_for(own), anchor), file=sys.stderr)
                return None
            hits = any_words_in(box, own, s_["ts"])
            if hits < (3 if (tb and ta) else 4):
                if why:
                    print("STILL? %s %s: only %d own words inside %s" % (s_["t0"], label_for(own), hits, [round(v) for v in box]), file=sys.stderr)
                return None
            # not where a window already drawn full stands - a window of ITS
            # OWN SIZE. `overlap` measures the share of the smaller box, so
            # a Finder standing on a maximised Obsidian scored 1.0 against
            # it and was refused for standing where it always stands: on
            # top of the editor. The cut-off Finder at 00:03:50 and the
            # vault-demo Finder at 00:00:50 were both lost to that. A window
            # covers this place only when it is not far bigger than it.
            # The place is TAKEN when another window of the same program
            # stands on it, or when the frame measured some window at that
            # very box. Obsidian's editor read to the right of the Finder is
            # the backdrop the Finder stands on, not a window in its place.
            for b in base_ + extra_:
                r_ = s_["rects"].get(id(b)) or pin.get(id(b))
                if r_ and overlap(box, r_) > 0.5 and (b.name == own.name or _agree(box, r_)):
                    if why:
                        print("STILL? %s %s: %s stands there" % (s_["t0"], label_for(own), label_for(b)), file=sys.stderr)
                    return None
            return box, anchor

        for s in spans:
            subjects = []
            still = {}        # a window carried from the moment it stood still at
            settled = set()   # states whose box the frame itself measured
            # A WINDOW THE FRAME DREW IN FULL, THAT NO FOCUS WINDOW COVERS,
            # IS A TOP-LAYER WINDOW AND MUST BE FILLED, not merely outlined.
            # Two Finders standing side by side are both plainly in view;
            # drawing one filled and the other a bare box says the screen
            # showed only one. The stretch is built from the windows the
            # reader followed, so a window nobody followed - present the whole
            # stretch, re-read only now and then - never joins the focus set
            # and falls through to the outline machinery. So before the
            # subjects are built, every measured frame window this stretch
            # shows, that no other frame window stands over (behind) and no
            # focus state already fills, is pulled in by the window whose own
            # carried place sits on it, and drawn full like any other subject.
            T0 = span_T.get(s["t0"])
            fw_here = frame_windows(s)
            base = list(s["states"])
            extra = []
            pin = {}                            # promoted state -> its measured rect

            def _lands(st_, r_):
                hb = home_at(st_, s["t0"])
                if not hb or not T0:
                    return 0.0
                b = onto(T0, hb)
                return furnish._within(r_, b) * furnish._within(b, r_)
            def _telling(words):
                """The words that say WHICH folder this is.

                A Finder's headings and the words in its Kind column stand in
                every Finder alike - Name, Date Modified, Size, Kind, Folder,
                Document - so counting them as agreement let a remembered
                window match a rectangle showing something else entirely.
                What tells one folder from another is its own rows.
                """
                out_ = set()
                for w in words:
                    n_ = norm(w)
                    if len(n_) < 4 or w in FINDER_WORDS:
                        continue
                    if re.match(r"^(folder|document|jsonl?|logfile|application)$", n_):
                        continue
                    if GLUED_DATE.search(w) or GLUED_SIZE.search(w):
                        continue
                    out_.add(n_)
                return out_

            def _contradicts(st_, r_):
                """What the reader read inside this rectangle NOW, set against
                what this window remembers showing.

                A carried box says where a window USED to be and what it
                showed THEN. At 00:01:10 the screen shows a Finder holding one
                row of the `projects` folder and the rectangle went to a
                remembered state of `.claude`, drawing six file names the
                screen was not showing.

                TWO TELLING WORDS ARE ENOUGH. At three this very case slipped
                through: of everything read inside that rectangle only
                `projects` and the one row's name survive the filter, because
                the rest is headings, a date and a Kind - and two words that
                a window does not know are already two too many.
                """
                m0_ = next((mm for mm in moments if mm["ts"] == s["t0"]), None)
                if not m0_:
                    return False
                read_ = []
                for p_ in m0_.get("panes") or []:
                    for it in draw2.items_of(p_):
                        b_ = it.get("box")
                        if b_ and it["text"].strip() and furnish._within(b_, r_) >= 0.8:
                            read_.append(it["text"])
                here = _telling(read_)
                if len(here) < 2:
                    return False              # too little read to contradict
                # ITS ROWS, NOT ITS PATH. A window's path bar says where it
                # SITS, not what it shows, and it ends at the row selected in
                # it as readily as at the folder on display. The `.claude`
                # state's path ends `.claude > projects`, so the one word that
                # told 00:01:10 apart - `projects` - matched the remembered
                # window and cancelled the very contradiction it was.
                t_ = st_.main_table()
                mine = set()
                if t_:
                    mine |= _telling([c for row in t_.rows for c in row["cells"] if c])
                # NOTHING AT ALL, not a small share. Everything read inside
                # the rectangle lands in `here` - the window's sidebar, and
                # whatever of its neighbour reaches in - so a share test on a
                # long list refuses a window that is plainly the right one:
                # at 00:01:20 seven of the vault-demo folders matched and the
                # window was still refused, drawn as an outline, and the gate
                # said so. A window that recognises NONE of what the screen
                # is showing where it is being asked to stand is the wrong
                # window; one word of agreement is enough to keep it.
                hit = sum(1 for w in here if any(w in k or k in w for k in mine))
                return hit == 0

            for r in fw_here:
                if any(o is not r and furnish._within(r, o) > 0.5 for o in fw_here):
                    continue                    # this window stands behind another
                if any(_lands(bst, r) > 0.25 for bst in base):
                    continue                    # a focus window already fills it
                pick, best = None, 0.2
                for own in states:
                    if own in base or own in extra or not own.has_content():
                        continue
                    sc = _lands(own, r)
                    if sc > best:
                        pick, best = own, sc
                if pick is not None and _contradicts(pick, r):
                    pick = None
                if pick is not None:
                    extra.append(pick)
                    # The rectangle the frame MEASURED for this window is the
                    # truth about where it stands NOW. A box carried from when
                    # the window was last read runs away under a later zoom -
                    # memory, read wide early on, maps half off the left edge
                    # by 02:20 and is dropped as off-screen, and the window it
                    # names is left an outline. Pin the promoted window to its
                    # measured rectangle, the same ground the focus windows
                    # stand on.
                    pin[id(pick)] = [float(v) for v in r]
            if os.environ.get("SN_STILL") == "2":
                print("STILL@ %s base %s extra %s" % (s["t0"], [label_for(b) for b in base], [label_for(b) for b in extra]), file=sys.stderr)
            for own in states:
                if own in base or own in extra or not own.has_content() or not is_real_window(own.name):
                    continue
                got = still_here(own, s, base, extra)
                if got is None:
                    continue
                box, anchor = got
                extra.append(own)
                pin[id(own)] = [float(v) for v in box]
                still[id(own)] = anchor
                if os.environ.get("SN_STILL"):
                    print("STILL %s %s carried from %s at %s" % (s["t0"], label_for(own), anchor,
                                                                 [round(v) for v in box]), file=sys.stderr)
            for st in base + extra:
                if st not in shown:
                    continue
                sl = state_slice(st, s["t0"], s["t1"])
                if sl is None and id(st) in still:
                    # drawn as it stood at the moment beside this one where
                    # it stood clear - the puzzle piece, never the window's
                    # whole gathered content
                    sl = state_slice(st, still[id(st)], still[id(st)])
                sl = sl or st
                # A SIDEBAR IS DRAWN AT ITS MEASURED SHARE IN A PICTURE TOO.
                # Without one the stylesheet's 160 units stood in, 15% of
                # the window where the frame had 28%, and the list spread
                # left over the sidebar's ground: at 00:00:30 every column
                # sat 70 px left of its place. The stretch's own measure
                # first, then the window's, then the widest window's, then
                # the house's.
                # The widest-window measure first, as the cards use: the
                # median share over a window's moments is the fault the
                # card rule names (vault-demo's came out at 53%, half the
                # window), and a raw share past 45% is no Finder sidebar.
                if st.name == "The Finder window":
                    def _side_ok(v):
                        return v if v and 0.1 <= v <= 0.45 else None
                    _own_share = (_side_ok(furnish.side_share_card(sl))
                                  or _side_ok(getattr(sl, "side_share", None))
                                  or _side_ok(furnish.side_share_card(st))
                                  or _side_ok(getattr(st, "side_share", None)))
                    sl.side_share = _own_share or house_share
                    sl._side_from_house = not _own_share
                if sl is not st:
                    # the desk's chrome stands all video; a stretch that did
                    # not re-read it still lives under it
                    sl.topwords = sl.topwords + [t for t in st.topwords
                                                 if not any(same_text(t[0], u[0]) for u in sl.topwords)]
                    polish(sl, states)
                    drop_guessed([sl])
                    # THE STRETCH'S LIST READ AS A TREE IS STILL ITS LIST. The
                    # whole window had this put right by `list_not_tree`; a
                    # stretch is rebuilt from its own panes and needs it again,
                    # or the vault-demo Finder at 00:00:30 draws its names with
                    # no columns, no path bar and no settled spelling.
                    if sl.main_table() is None and st.main_table() is not None:
                        _wt = st.main_table()
                        _wk = {fold(flat((r.get("cells") or [""])[0])) for r in _wt.rows
                               if (r.get("cells") or [""])[0]}
                        for q in [x for x in sl.parts if x["fam"] == "tree"
                                  and getattr(x["model"], "lines", None)]:
                            _convert_tree(sl, q, [(_wt, _wk, st)])
                    sidebar_from_panes(sl, house_side)
                    tidy_side(sl.main_table(), house_side, sl.title)
                    respell_from(sl, st)      # so the mend's walk meets the settled names
                    mend_cells(sl, st)
                    if sl.main_table():
                        fold_twins(sl.main_table(), 0)
                        drop_glued(sl.main_table())
                    # the bar ends at the folder the window shows, and the
                    # title bar names it: a stretch whose reading of the bar
                    # stopped short (`... > 02 Co` under a window titled
                    # `Assets`) gets the folder back on the end
                    _st_t = sl.main_table()
                    if _st_t and _st_t.path and sl.title and not getattr(st, "title_from_path", False):
                        _st_t.path = end_at_folder(_st_t.path, sl.title)
                    # A CRUMB THE STRETCH MISREAD TAKES THE SETTLED SPELLING;
                    # a crumb Finder itself cut short (`-Users-jaredrh`) is
                    # what the frame shows and stays. `prjects` stood on the
                    # 00:01:40 bar under a settled bar reading `projects`.
                    _whole_t = st.main_table()
                    if _st_t and _st_t.path and _whole_t and _whole_t.path:
                        _fixed = []
                        for c_ in _st_t.path:
                            f_ = flat(c_)
                            def _md_pair(x_, y_):
                                return (x_.endswith("md") and x_[:-2] == y_) or (y_.endswith("md") and y_[:-2] == x_)
                            hit_ = next((w_ for w_ in _whole_t.path if crumb_same(c_, w_)
                                         or (len(f_) >= 5 and f_[:1] == flat(w_)[:1] and abs(len(f_) - len(flat(w_))) <= 2
                                             and not _md_pair(f_, flat(w_))
                                             and difflib.SequenceMatcher(None, f_, flat(w_), autojunk=False).ratio() >= 0.85)), None)
                            _caps = lambda x_: sum(ch.isupper() for ch in x_)
                            if hit_ is not None and f_ != flat(hit_) and not flat(hit_).startswith(f_):
                                _fixed.append(hit_)
                            elif hit_ is not None and f_ == flat(hit_) and hit_ != c_ and _caps(hit_) > _caps(c_):
                                _fixed.append(hit_)         # `(info Product)` takes the settled `(Info Product)`
                            else:
                                _fixed.append(c_)
                        if os.environ.get("SN_PATH") and _fixed != list(_st_t.path):
                            print("PATHFIX %s %s: %s -> %s" % (s["t0"], label_for(st), _st_t.path, _fixed), file=sys.stderr)
                        _st_t.path = _fixed
                    respell_from(sl, st)
                    strip_furniture(sl, strip_at)
                    drop_side_prefix(sl)
                    drop_crumb_rows(sl, _all_crumbs)
                    if bar_title(sl, s["size"][1]):
                        sl.title = None
                    sl.title = sl.title or st.title
                    fd, sd = st.main_doc(), sl.main_doc()
                    # a stretch that showed nothing in the note pane keeps
                    # showing nothing: the window's heading belongs to the
                    # note, and the note was not on the screen then
                    if fd and sd and fd.lines and sd.lines and sd.lines is not fd.lines \
                            and "sn-h1" in fd.lines[0][1] and not any(
                                fold(flat(t)) == fold(flat(fd.lines[0][0])) for t, _ in sd.lines[:3]):
                        sd.lines.insert(0, fd.lines[0])
                    mend_slice_tree(sl, st)
                # How far apart THIS window set one row from the next, on
                # THIS frame. A file list and a note's prose are set at
                # different pitches, so one figure for the whole screen
                # draws one of them wrong; and the pitch is what the screen
                # and the style sheet have in common, where a glyph's
                # measured box and a font-size are not the same quantity.
                def pitch_of(p_):
                    """How far apart this pane set one row from the next, in
                    the frame's own pixels. The reader's own row boxes are
                    the measurement - one box per row, already sorted out
                    from the words - and they are kept in the pane image's
                    coordinates, which stand `scale` times the frame."""
                    d_ = p_.get("data") or {}
                    tops = []
                    for b_ in (d_.get("blocks") or []):
                        tops += [rb[1] for rb in (b_.get("row_boxes") or [])
                                 if isinstance(rb, (list, tuple)) and len(rb) >= 4]
                    for key in ("rows", "body_rows"):
                        tops += [x["y0"] for x in (d_.get(key) or [])
                                 if isinstance(x, dict) and "y0" in x]
                    tops = sorted(set(tops))
                    if len(tops) < 4:
                        return None
                    gaps = [b - a for a, b in zip(tops, tops[1:]) if 0 < b - a < 1200]
                    if len(gaps) < 3:
                        return None
                    # rows are set evenly, so the pitch is the gap the most
                    # gaps agree on - a heading's extra space does not vote
                    best = max(gaps, key=lambda g: sum(1 for h in gaps if abs(h - g) <= 0.15 * g))
                    like = [h for h in gaps if abs(h - best) <= 0.15 * best]
                    if len(like) < 3:
                        return None
                    # The row boxes are kept in the pane image's own pixels,
                    # and that image was read at a whole-number upscale. The
                    # upscale is not always written down, so it is taken from
                    # how far the rows reach against the pane's own height.
                    high = p_["box"][3] - p_["box"][1]
                    up = float(d_.get("scale") or 0)
                    if not up and high > 0:
                        up = max(1.0, round(max(tops) / high))
                    return (len(tops), (sum(like) / len(like)) / max(1.0, up))
                # A window keeps one pitch: what changes between moments is
                # how far the video was zoomed in. So every moment of this
                # WINDOW votes - each one's measured pitch taken back out of
                # its own zoom - and the vote is brought into this stretch's
                # zoom. One moment on its own is far too noisy to size a
                # window by: a pane can be a sliver, or missed altogether.
                sl._doc_pad = getattr(st, "_doc_pad", 0)
                # the line length this stretch's own moments measured, so a
                # picture shows the note as wide as it ran THEN
                mine = [sn.doc_wide for t_, sn in st.moments()
                        if sn.doc_wide is not None and t_ in s["ts"]]
                sl._doc_wide = (round(100 * med(sorted(mine))) if mine
                                else getattr(st, "_doc_wide", 0))
                # THE FAULT, DELETED. This line read `sl.rects, sl.measured =
                # st.rects, st.measured`: the stretch was handed the WHOLE
                # window's per-moment tables, so a picture of 00:01:00 could be
                # shaped by an edge measured at 00:03:50. A stretch already
                # holds its own moments -- `state_slice` replays them through
                # `absorb`, which records a rect and a measured flag for each --
                # so there was never anything to borrow, only something to
                # overwrite it with.
                # The shape the window really had. Where the reader measured
                # its edges off the frame, those edges stand. Otherwise the
                # window's own place - every reading of it carried home and
                # put together - is brought into this stretch's zoom: the
                # same box its outline would get, so a window drawn full and
                # the same window drawn as an outline never disagree, and a
                # window is not drawn round whichever corner of it had words
                # at that moment.
                _tr = os.environ.get("SN_TRACE")
                if s["t0"] in getattr(st, "measured", set()):
                    shape = s["rects"].get(id(st)) or st.rects.get(s["t0"])
                    if shape:
                        settled.add(id(st))
                    if _tr:
                        print("TRACE %s measured shape %s (s-rects %s, st-rects %s)"
                              % (s["t0"], shape, s["rects"].get(id(st)),
                                 st.rects.get(s["t0"])), file=sys.stderr)
                else:
                    # the frame's own rectangle round this window's panes
                    # comes first: it is measured on this very frame
                    shape = rect_over_panes(st, s) or carry_by_neighbour(st, s)
                    if not shape:
                        T0, hb = span_T.get(s["t0"]), home_at(st, s["t0"])
                        shape = (onto(T0, hb) if (T0 and hb) else None)
                shape = shape or s["rects"].get(id(st)) or span_rect(st, s["t0"]) or st.rect
                # A box as wide as the whole frame is the reader's own strip,
                # not a window: it read a slab of the screen and the window's
                # rect came back as the slab. This window's OWN rows say
                # which rectangle on the frame it really is.
                if shape and shape[2] - shape[0] >= 0.9 * Wf:
                    by_rows = rect_over_panes(st, s)
                    if by_rows and by_rows[2] - by_rows[0] < 0.9 * Wf:
                        shape = by_rows
                        settled.discard(id(st))
                # A window holds the panes it was read from. Where a box
                # worked out from readings comes out narrower than the
                # panes themselves - a note window drawn as just its file
                # tree - the panes widen it, because the reader cut them
                # off THIS frame and they stood inside this window.
                if shape and id(st) not in settled:
                    lo_x, hi_x = shape[0], shape[2]
                    for m_, g_ in getattr(st, "pieces", ()):
                        if m_["ts"] not in s["ts"]:
                            continue
                        for p_ in (g_.get("panes") or []):
                            b_ = p_.get("box")
                            if not b_ or b_[2] - b_[0] > 0.5 * Wf:
                                continue      # a slab, not one window's pane
                            lo_x, hi_x = min(lo_x, b_[0]), max(hi_x, b_[2])
                    # A pane is filed under the window it was cut from, so
                    # a window's panes really are its own and may be as wide
                    # as they like - what they may not do is reach past the
                    # screen, because nothing was shown there.
                    if hi_x - lo_x <= Wf:
                        if _tr and (lo_x != shape[0] or hi_x != shape[2]):
                            print("TRACE %s panes widen %s -> %s"
                                  % (s["t0"], shape, [lo_x, shape[1], hi_x, shape[3]]),
                                  file=sys.stderr)
                        shape = [lo_x, shape[1], hi_x, shape[3]]
                if id(st) in pin:
                    # measured off this very frame: it outranks any box worked
                    # out from where the window's words happened to sit
                    shape = list(pin[id(st)])
                    settled.add(id(st))
                sl.rect = shape
                # A large window the frame never measured -- Obsidian's editor,
                # maximised, with no rectangle to close -- cannot be FILLED
                # honestly: drawn at a box worked out from where its words sat
                # it lands maximised at the wrong place and misses the frame.
                # It gets a card (its content, view two) by being a real
                # window, but in the desktop picture it stays a named outline
                # until the reader learns to measure it. A moment where the
                # frame DID measure it (settled) draws it full as any window.
                # THE READER HAS LEARNED TO MEASURE IT, which is the very
                # condition the rule above was written to wait for. A window
                # the screen CUTS OFF closes no rectangle in `shapes` and so
                # never reached `st.measured`; `bigwin` measures it from the
                # corner its two drawn edges make. Where a big window holds
                # this state's own worked-out box, that box is finished and
                # the window is drawn full like any other -- which is what
                # puts Obsidian's text on the screen instead of a label.
                # Only a state whose OWN box is already big may claim one: a
                # Finder standing inside a maximised window must not.
                _would_skip = (st.name == "The Obsidian window" and id(st) not in settled
                               and (frame_windows(s)
                                    or any(o.name != "The Obsidian window" and o.has_content()
                                           for o in base + extra)))
                if (_would_skip and shape
                        and shape[2] - shape[0] >= 0.5 * Wf
                        and shape[3] - shape[1] >= 0.3 * Hf):
                    cands = [b for b in frame_bigwins(s)
                             if furnish._within(shape, b) > 0.7]
                    if cands:
                        # THE BOX WHOSE TOP IS NEAREST THIS WINDOW'S OWN.
                        # On a desktop where one big window stands inside
                        # another -- Obsidian over a maximised browser --
                        # both contain the state's box, and taking the
                        # smaller by area still handed one Obsidian state
                        # the browser's rectangle, 131 pixels too high.
                        # A window's top edge is the thing its own content
                        # begins under.
                        shape = list(min(cands, key=lambda b: (
                            abs(b[1] - shape[1]), (b[2] - b[0]) * (b[3] - b[1]))))
                        sl.rect = shape
                        settled.add(id(st))
                        sl._cut_by_screen = False
                        st._cut_by_screen = False
                _obs_behind = (st.name == "The Obsidian window" and id(st) not in settled
                               and (frame_windows(s)
                                    or any(o.name != "The Obsidian window" and o.has_content()
                                           for o in base + extra)))
                if _obs_behind:
                    pass                       # stands behind others -> outline, card holds its content
                elif sl.has_content() and shape:
                    subjects.append((st, sl, shape))
            if not subjects:
                continue
            # The frame draws its windows as rectangles, and those rectangles
            # were measured off it. A box worked out from where a window's
            # words sat is a guess about its edges; a rectangle on the frame
            # IS its edges. So every box is pulled onto the measured
            # rectangle it belongs to, which is what stops a window being
            # drawn round whichever corner of it happened to hold text.
            # A BOX THE FRAME MEASURED IS FINISHED. The snap exists for a
            # box worked out from where a window's words sat; run over a
            # measured rectangle it pulls the window onto whichever other
            # rectangle scores best - a panel inside it, a card, a variant
            # of its own edges - and the window is then drawn up to 256
            # pixels from where the screen had it. Measurement outranks
            # inference, and that holds AFTER the box is chosen as much as
            # before.
            if os.environ.get("SN_TRACE"):
                for _stx, _sl, _sh in subjects:
                    if id(_stx) not in settled:
                        print("TRACE %s before snap %s -> after %s"
                              % (s["t0"], _sh, snap_to_frame(_sh, s)), file=sys.stderr)
            subjects = [(stx, sl, shape if id(stx) in settled
                         else snap_to_frame(shape, s))
                        for stx, sl, shape in subjects]
            # ONE PLACE, ONE WINDOW, and that holds for a window drawn FULL
            # as much as for an outline. The screen has one Obsidian window
            # at 00:00:00 and the reader recorded two states of it -- one
            # holding the note, one holding the strip along the top -- so
            # once both could be pinned to a measured box the picture drew
            # two Obsidian windows, one over the other, each with its own
            # title bar. Two windows of the same program that do NOT overlap
            # are two windows (the two Finders), and are left alone.
            keep = []
            for stx, sl, shape in subjects:
                clash = None
                for i, (ox, ol, osh) in enumerate(keep):
                    if ox.name == stx.name and shape and osh and \
                            max(furnish._within(shape, osh),
                                furnish._within(osh, shape)) > 0.7:
                        clash = i
                        break
                if clash is None:
                    keep.append((stx, sl, shape))
                    continue
                # the one that says more about the window is the one drawn:
                # more of its own readings placed inside its own box
                ox, ol, osh = keep[clash]
                if len(sl.said_html() or ()) > len(ol.said_html() or ()):
                    keep[clash] = (stx, sl, shape)
            subjects = keep
            for stx, sl, shape in subjects:
                sl.rect = shape
                # A box the frame itself drew: its edges are measured, and
                # nothing worked out from where words sat may move them.
                # The rectangles the READER measured count as drawn here -
                # they are the same measurement, taken when the frame was
                # read - and asking the picture for its rectangles again
                # answers with a slightly different set, so a window whose
                # box came straight from the record failed this test and
                # every later rule then felt free to move it.
                sl._on_frame = (id(stx) in settled
                                or any(shape == r for r in frame_rects(s)))
            # A box still worked out from where words sat is squared up
            # against what the frame DID measure. Two things settle it: it
            # cannot reach into a window whose edges were measured, and
            # where a measured rectangle stands inside it running most of
            # its height, that rectangle is a pane of this same window and
            # its top and foot are this window's top and foot.
            # A rectangle the frame drew that no window claimed is still a
            # window - the screen drew it. Where a box that was worked out
            # from where words sat overlaps exactly one such rectangle, the
            # two are the same window, and the measured one is the truth.
            taken = [sh for _, sl, sh in subjects if getattr(sl, "_on_frame", False)]
            spare = [r for r in frame_rects(s)
                     if not any(furnish._within(r, t) > 0.7 or furnish._within(t, r) > 0.7
                                for t in taken)]
            for stx, sl, shape in subjects:
                if getattr(sl, "_on_frame", False):
                    continue
                near_ = [r for r in spare if furnish._within(r, shape) > 0.7
                         and furnish._within(shape, r) > 0.4]
                if len(near_) == 1:
                    sl.rect = list(near_[0])
                    sl._on_frame = True
            subjects = [(stx, sl, sl.rect) for stx, sl, _ in subjects]
            fixed = [sh for _, sl, sh in subjects if getattr(sl, "_on_frame", False)]
            for stx, sl, shape in subjects:
                if getattr(sl, "_on_frame", False):
                    continue
                box = list(shape)
                for m in fixed:
                    tall = min(box[3], m[3]) - max(box[1], m[1])
                    wide = min(box[2], m[2]) - max(box[0], m[0])
                    if tall > 0.5 * (box[3] - box[1]):
                        if m[0] <= box[0] < m[2] < box[2]:
                            box[0] = m[2]
                        elif box[0] < m[0] < box[2] <= m[2]:
                            box[2] = m[0]
                    if wide > 0.5 * (box[2] - box[0]):
                        if m[1] <= box[1] < m[3] < box[3]:
                            box[1] = m[3]
                        elif box[1] < m[1] < box[3] <= m[3]:
                            box[3] = m[1]
                inside = [r for r in frame_rects(s)
                          if box[0] <= r[0] and r[2] <= box[2]
                          and box[1] <= r[1] and r[3] <= box[3]
                          and r[3] - r[1] >= 0.5 * (box[3] - box[1])]
                if inside:
                    r = max(inside, key=lambda r: r[3] - r[1])
                    box[1], box[3] = r[1], r[3]
                    # A pane running the window's whole height sits flush
                    # against the side it is on, so that side of the pane is
                    # that side of the window - but only where no other pane
                    # was measured further out, and only on the side where
                    # the window does not go on past it.
                    if r[0] <= min(x[0] for x in inside) and r[2] < box[2]:
                        box[0] = r[0]
                    if r[2] >= max(x[2] for x in inside) and r[0] > box[0]:
                        box[2] = r[2]
                sl.rect = box
            subjects = [(stx, sl, sl.rect) for stx, sl, _ in subjects]
            # deepest first: the bigger window lies under the smaller one
            subjects.sort(key=lambda x: -(x[2][2] - x[2][0]) * (x[2][3] - x[2][1]))
            # the windows truly behind, their own content where it sat: told
            # by a fragment read around the front windows, or by another
            # window's note or tree filed onto a front window's own panes
            sub_states = [stx for stx, _, _ in subjects]
            T = span_T.get(s["t0"])
            if T is None:
                T = last_T          # nothing readable moved between the two
            # A FIT UNDER 1.15 IS NO ZOOM, HERE AS IN THE HOME READS: the
            # 0.83 read off two full-screen frames sized their type by it
            # while their boxes came home unchanged, and the note at
            # 00:04:10 was drawn a sixth too small (0.62 to 0.57).
            if T and T[0] < 1.15:
                T = (1.0, 0.0, 0.0)
            last_T = T
            bar_words = max((bar_at[t] for t in s["ts"] if bar_at.get(t)),
                            key=len, default=[])
            clock = next((clock_at[t] for t in s["ts"] if clock_at.get(t)), "")
            barred = any(t in bar_seen for t in s["ts"])

            kz_now = T[0] if T else 1.0
            S_now = max(0.05, kz_now * furnish.UI_TXT / furnish.CSS_TXT)

            def span_pad(st_, top):
                seen = next((sn.h1 for t_, sn in st_.moments()
                             if sn.h1 and t_ in s["ts"]), None)
                if seen is None:
                    return getattr(st_, "_doc_pad", 0)
                pad = (seen[1] - top) * furnish.CANVAS_W / Wf / S_now - 60
                return round(pad) if pad > 12 else 0

            # Last of all, once every box has been pulled onto what the
            # frame measured: a window holds its own words. A box that
            # ended up beside them or inside them leaves those words
            # standing on bare desktop, with the window they belong to
            # drawn somewhere else on the same picture.
            for i_, (stx, sl, shape) in enumerate(subjects):
                if not getattr(sl, "_on_frame", False):
                    sl.rect = hold_words(hold_panes(list(shape), stx, s["ts"], Wf),
                                         stx, s["ts"], Wf, Hf)
            subjects = [(stx, sl, sl.rect) for stx, sl, _ in subjects]
            for stx, sl, shape in subjects:
                sl._doc_pad = span_pad(stx, shape[1])
                # EACH BLOCK OF THE NOTE AT THE HEIGHT IT SAT, in the
                # window's own unit, so it lands there at any page width.
                # The first block flows from the top pad as before; every
                # later one is placed by its pane's measured top.
                # WHERE THE WINDOW PUT ITS OWN COLUMNS, measured off this
                # stretch's panes. The drawn window has two columns and the
                # real one often has five, so taking only the TREE's share
                # and giving the note everything left over overshoots: it
                # made 00:04:10 worse, not better. What the frame states
                # plainly is where the note's own pane BEGINS and how wide
                # it is; the tree column runs up to that edge (tree plus the
                # margin beside it, which is how it reads), and whatever
                # lies beyond the note's pane is left blank, because the
                # picture does not draw what stood there.
                if shape and shape[2] > shape[0]:
                    dl = dr = None
                    for m_, g_ in getattr(stx, "pieces", ()):
                        if m_["ts"] not in s["ts"]:
                            continue
                        for q_ in (g_.get("panes") or []):
                            if q_.get("kind") != "an open document":
                                continue
                            b_ = q_.get("box")
                            if not b_ or b_[2] - b_[0] < 0.25 * (shape[2] - shape[0]):
                                continue      # a sliver, not the note's pane
                            if dl is None or (b_[2] - b_[0]) > (dr - dl):
                                dl, dr = b_[0], b_[2]
                    if dl is not None and shape[0] <= dl < dr <= shape[2] + 4:
                        w_ = float(shape[2] - shape[0])
                        for m_, g_ in getattr(stx, "pieces", ()):
                            if m_["ts"] not in s["ts"]:
                                continue
                            for q_ in (g_.get("panes") or []):
                                if q_.get("kind") != "a file tree":
                                    continue
                                b_ = q_.get("box")
                                if b_ and b_[2] <= dl:
                                    sl._tree_fr = max(4, round(
                                        100.0 * (b_[2] - shape[0]) / w_))
                sl._doc_blocks = []
                d_ = sl.main_doc()
                if d_ is not None and len(getattr(d_, "blocks", ())) > 1 and shape:
                    step_ = getattr(sl, "_row_step", 0)
                    k_ = max(0.05, step_ / furnish.ROW_H) if step_ else S_now
                    for i_, (top_, foot_, texts_) in enumerate(sorted(d_.blocks)):
                        if i_ == 0:
                            sl._doc_blocks.append((None, texts_))
                            continue
                        u_ = (top_ - shape[1]) * furnish.CANVAS_W / Wf / k_ - 60
                        sl._doc_blocks.append((round(u_) if u_ > 0 else None, texts_))
                # How tall a row stands here: this window's own share of
                # its width, voted across every moment of it in the whole
                # run, taken against the width it is drawn at NOW. One
                # moment on its own is far too noisy to size a window by -
                # a pane can be a sliver, or missed altogether.
                # a hair of margin: where the frame's edge stood in for a
                # window's side, the rectangle stops a pixel or two short
                # of it, and that side is still the screen's, not the
                # window's
                mx, my = max(4.0, 0.005 * Wf), max(4.0, 0.005 * Hf)
                cut_x = shape[0] < mx or shape[2] > Wf - mx
                cut_y = shape[1] < my or shape[3] > Hf - my
                # A WINDOW WHOSE EDGE IS THE SCREEN'S EDGE IS NOT CUT OFF BY
                # IT. "Cut off" means the window carries on past the frame,
                # so its drawn width is not its own and cannot size its
                # rows. A window `bigwin` measured was TRACED to that edge:
                # the box is its on-screen extent, and its width is its
                # width. Read as cut off both ways, Obsidian fell through to
                # a width carried from another moment and its rows came out
                # at 5.7 where the Finders beside it stood at 9.5 -- the
                # whole window drawn about a quarter of its true size.
                if getattr(sl, "_cut_by_screen", None) is False:
                    cut_x = cut_y = False
                share = pitch_home.get(stx.name) or pitch_home.get("*") or 0.0
                if not cut_x and share:
                    span_now = share * (shape[2] - shape[0])
                elif not cut_y and (tall_home.get(stx.name)
                                    or tall_home.get("*")):
                    # cut off at the side, so its drawn width is not the
                    # window's width - but its height is still the window's
                    # own, and a row stands in a fixed share of that too
                    tall = tall_home.get(stx.name) or tall_home.get("*")
                    span_now = tall * (shape[3] - shape[1])
                else:
                    # cut off both ways: the window's width at home carried
                    # forward on the zoom the frame itself gives
                    hb_now = home_at(stx, s["t0"])
                    # the stretch's own fit, with the no-zoom rule applied
                    # the same way as everywhere else -- the raw 0.83 here
                    # against a home box carried as itself drew the window
                    # a sixth too narrow and its rows a sixth too small
                    kzf = (T[0] if T else 1.0) or 1.0
                    wide = (hb_now[2] - hb_now[0]) * kzf if hb_now else 0.0
                    span_now = share * wide
                sl._row_step = span_now * furnish.CANVAS_W / Wf
                sl._step_sure = not (cut_x or cut_y)
                # A PITCH MEASURED ON THIS WINDOW'S OWN ROWS OUTRANKS A
                # SHARE CARRIED FROM ANOTHER WINDOW. Everything above works
                # a window's pitch out from a share held per program, which
                # assumes every window of that program sets its rows the
                # same. Finder does not: its list density is a per-window
                # setting, and at 00:03:00 one Finder stands at 42 frame
                # pixels a row where the other stands at 81.
                own = (getattr(sl, "_pitch_at", {}).get(s["t0"])
                       or getattr(stx, "_pitch_at", {}).get(s["t0"]))
                if own:
                    sl._row_step = own * furnish.CANVAS_W / Wf
                    sl._step_sure = False      # and no median may replace it
                    sl._pitch_measured = True
                if os.environ.get("SN_PITCH"):
                    print("PITCH %s %-28s shape=%s own=%s step=%.1f sure=%s cut=%s/%s"
                          % (s["t0"], label_for(stx, s["t0"]), [round(v) for v in shape] if shape else None,
                             own, sl._row_step, sl._step_sure, cut_x, cut_y), file=sys.stderr)

            # Two windows of the same program standing on one screen set
            # their rows at the SAME pitch: the pitch belongs to the screen,
            # not to the window, and what changes between frames is only how
            # far the video zoomed. So a window cut off by the frame's edge,
            # whose own width says nothing, takes the pitch from the window
            # beside it that the frame shows whole.
            sure = {}
            for stx, sl, _ in subjects:
                _snx = (sl.at(s["t0"]) or stx.at(s["t0"]))
                whole_ = getattr(sl, "_pitch_measured", False) and not (_snx is not None and _snx.pitch_cut)
                if (getattr(sl, "_step_sure", False) or whole_) and getattr(sl, "_row_step", 0):
                    sure.setdefault(stx.name, []).append(sl._row_step)
            for stx, sl, _ in subjects:
                had = sure.get(stx.name)
                if not had:
                    continue
                if not getattr(sl, "_pitch_measured", False):
                    sl._row_step = med(sorted(had))
                    continue
                # A PITCH MEASURED ON A LIST THE SCREEN CUT OFF IS A WEAK
                # MEASUREMENT: read loose, its two columns come back as
                # separate rows and the gaps halve. Run 19c measured 42 against
                # 81 on one screen and wrote it up as Finder's per-window
                # density; the frame itself shows both lists at one pitch (64
                # frame pixels, 00:03:00, checked by eye). Where a neighbour
                # measured whole on the same frame disagrees by more than a
                # quarter, the neighbour's pitch is the screen's.
                _sn = (sl.at(s["t0"]) or stx.at(s["t0"]))
                if _sn is not None and _sn.pitch_cut:
                    med_ = med(sorted(had))
                    if abs(med_ - sl._row_step) > 0.25 * med_:
                        sl._row_step = med_

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
            behinds, carded, behind_state = [], set(), {}
            lo, hi = s["t0"], s["t1"]
            # rectangles the frame drew that no window in front stands on:
            # the screen drew them, so a window IS there, and a window
            # whose carried place lands on one is on the screen whatever
            # else can be said for it
            held = [r for _, _, r in subjects if r]
            spare_r = [r for r in frame_rects(s)
                       if not any(furnish._within(r, c) > 0.6
                                  or furnish._within(c, r) > 0.6 for c in held)]
            for own in states:
                if own in sub_states or id(own) in carded:
                    continue
                # a carried place needs the map between moments; a window
                # placed by its own words this stretch does not, so a stretch
                # with no map still draws what its own frame shows
                hb = home_at(own, s["t0"]) if T is not None else None
                # a long line of its own text read this stretch places the
                # window more surely than any carried box
                keys = own_words.get(id(own)) or set()
                long_hits = []
                for t in s["ts"]:
                    for key, b in (words_of.get(t) or {}).items():
                        # A word of this window's own, read at this moment,
                        # stands inside it. A window BEHIND is read in
                        # fragments - the windows in front cut its lines up
                        # - so a run of eight letters sitting inside one of
                        # its own lines counts, where waiting for a whole
                        # line loses the window altogether.
                        if (len(key) >= 5 and key in keys) or (
                                len(key) >= 6 and any(
                                    key in sk for sk in keys)) or (
                                len(key) >= 12 and any(
                                    sk in key for sk in keys)):
                            long_hits.append(b)
                if hb is None:
                    # A WINDOW WITH NO PLACE OF ITS OWN THIS STRETCH IS STILL
                    # ON THE SCREEN WHERE ITS OWN WORDS ARE. Obsidian stood
                    # behind two Finder windows for the first four minutes
                    # of a video, its tree down the left and its note down
                    # the right, and because no moment had measured its
                    # edges it was never drawn at all: the picture showed
                    # two Finders floating on black with the note's words
                    # scattered loose around them. Its words were read, and
                    # they were read from one side of the screen to the
                    # other - which is where a window that fills the screen
                    # is. A window whose words reach across half the screen
                    # both ways fills it; a smaller spread is the window's
                    # own reach, and the frame's rectangles may tighten it.
                    if os.environ.get("UIX_WHY") == s["t0"]:
                        print(f"   no home {label_for(own)!r}: {len(long_hits)} own words read this stretch",
                              file=sys.stderr)
                    if len(long_hits) < 2:
                        continue
                    box = [min(b[0] for b in long_hits), min(b[1] for b in long_hits),
                           max(b[2] for b in long_hits), max(b[3] for b in long_hits)]
                    if box[2] - box[0] >= 0.5 * Wf and box[3] - box[1] >= 0.5 * Hf:
                        box = [0.0, 0.0, float(Wf), float(Hf)]
                else:
                    box = onto(T, hb)
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
                on_rect = any(furnish._within(r, box) > 0.6
                              or furnish._within(box, r) > 0.6 for r in spare_r)
                alive = (id(own) in seen_here or len(long_hits) >= 2
                         or on_rect
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
                behind_state[len(behinds)] = own
                behinds.append((label_for(own, s["t0"]), snap_to_frame(list(box), s)))
            # An outline is a window too, and a rectangle the frame drew
            # that no window in front claimed is the window it outlines. A
            # box worked out from where words sat can run a window off the
            # side of the screen; the measured rectangle cannot.
            claimed = [sh for _, _, sh in subjects]
            free = [r for r in frame_rects(s)
                    if not any(furnish._within(r, c) > 0.7
                               or furnish._within(c, r) > 0.7 for c in claimed)]
            on_rect_k = set()
            # A box is judged by the part of it that is ON the screen. These
            # boxes are worked out across zooms and often reach past the
            # frame; the part beyond the edge was never shown, and counting
            # it makes a window look far wider than it stood.
            for k, (tag_, box_) in enumerate(behinds):
                cut = [max(0.0, box_[0]), max(0.0, box_[1]),
                       min(float(Wf), box_[2]), min(float(Hf), box_[3])]
                if cut[2] > cut[0] and cut[3] > cut[1]:
                    behinds[k] = (tag_, cut)
            for k, (tag_, box_) in enumerate(behinds):
                if any(furnish._within(box_, r) > 0.9
                       and furnish._within(r, box_) > 0.9 for r in free):
                    on_rect_k.add(k)
                    continue                       # already on its rectangle
                # both ways round: the rectangle mostly inside this box AND
                # this box mostly inside the rectangle. A window that fills
                # the screen holds every other window's rectangle inside
                # it, and one of those is not the window.
                # A window that was never measured anywhere near this wide
                # cannot be this wide now: a box carried across zooms has
                # run away, and the rectangle the frame drew is the window.
                own_k = behind_state.get(k)
                ever = [own_k.rects[t] for t in getattr(own_k, "measured", ())
                        if own_k and own_k.rects.get(t)] if own_k else []
                small = bool(ever) and max(
                    (r[2] - r[0]) for r in ever) < 0.7 * Wf
                grown = (box_[2] - box_[0]) > 0.9 * Wf
                # or where it reaches across a window the frame measured
                # and another window is drawn on: a window that never
                # filled the screen does not stand behind AND beside the
                # window in front of it - its own rectangle is the one the
                # frame drew where no one else stands.
                over = any(furnish._within(c, box_) > 0.4 for c in claimed)
                near_ = [r for r in free
                         if furnish._within(r, box_) > 0.7
                         and (furnish._within(box_, r) > 0.5
                              or (small and (grown or over)))
                         and not (sidebar_window(r, s["t0"])
                                  and not tag_.startswith("Finder"))]
                if len(near_) == 1:
                    behinds[k] = (tag_, list(near_[0]))
                    on_rect_k.add(k)
            # One program, one truth. Where several outlines of the SAME
            # program are drawn and any of them stands on a rectangle the
            # frame measured, the ones that do not are that window's older
            # place still carried in the record - they are dropped, and the
            # fullest name among them goes onto the ones that stand on the
            # screen's own rectangle. Left in, the biggest of them wins the
            # merge and the window is drawn where it never was.
            best_name = {}
            for k, (tag_, _b) in enumerate(behinds):
                app = tag_.split(":")[0].strip()
                if k in on_rect_k and len(tag_) > len(best_name.get(app, "")):
                    best_name[app] = tag_
            keep = []
            for k, (tag_, box_) in enumerate(behinds):
                app = tag_.split(":")[0].strip()
                if app in best_name and k not in on_rect_k:
                    continue
                if k in on_rect_k and len(best_name.get(app, "")) > len(tag_):
                    tag_ = best_name[app]
                keep.append((k, tag_, box_))
            on_rect_k = {i for i, (k, _t, _b) in enumerate(keep) if k in on_rect_k}
            behind_state = {i: behind_state.get(k) for i, (k, _t, _b) in enumerate(keep)}
            behinds = [(t, b) for _k, t, b in keep]

            # A box standing on a rectangle the frame MEASURED is not moved
            # by panes or words: measurement outranks inference, and
            # widening it afterwards puts the window back where it never was.
            for k, (tag_, box_) in enumerate(behinds):
                own_ = behind_state.get(k)
                if own_ is not None and k not in on_rect_k:
                    box_ = hold_panes(list(box_), own_, s["ts"], Wf)
                    behinds[k] = (tag_, hold_words(box_, own_,
                                                   s["ts"], Wf, Hf))
            # THE PICTURE'S WINDOWS COME FROM THE FRAME. Every window the
            # screen drew gets a box: the ones drawn in full, and an outline
            # for every other. Built the other way round - from the windows
            # the reader happened to follow - a window the reader never
            # named is simply absent from the picture, and the picture says
            # the screen showed nothing there.
            #
            # A name is found for each by asking which of the windows the
            # reader DID follow stands on that rectangle: the one whose own
            # box covers it best, else the one whose own words were read
            # inside it. A window nobody can name is still drawn, and says
            # so.
            real_w = [r for r in frame_windows(s)]
            held = [sh for _, _, sh in subjects if sh]
            spare_w = [r for r in real_w
                       if not any(furnish._within(r, c) > 0.7
                                  and furnish._within(c, r) > 0.7 for c in held)]
            if True:
                fresh, taken_k = [], set()
                for r in spare_w:
                    if sidebar_window(r, s["t0"]):
                        # this rectangle's own furniture names it, whatever
                        # else showed through it
                        near_f = [(t_, b_) for t_, b_ in behinds
                                  if t_.startswith("Finder")
                                  and furnish._within(r, b_) * furnish._within(b_, r) > 0.15]
                        fresh.append((near_f[0][0] if near_f else "Finder", list(r)))
                        continue
                    best, bk = 0.0, None
                    for k, (tag_, box_) in enumerate(behinds):
                        if k in taken_k:
                            continue
                        v = furnish._within(r, box_) * furnish._within(box_, r)
                        if v > best:
                            best, bk = v, k
                    tag = behinds[bk][0] if (bk is not None and best > 0.15) else ""
                    if not tag:
                        # the window whose OWN words stand inside this
                        # rectangle most - not the first that happens to
                        # have one, which names a window for whichever
                        # program the loop reached first
                        pick, most = None, 0
                        for own in states:
                            if own in sub_states:
                                continue
                            n = words_in(r, own, s["ts"])
                            if n > most:
                                pick, most = own, n
                        if pick is not None and most >= 2:
                            tag = label_for(pick, s["t0"])
                    if bk is not None and best > 0.15:
                        taken_k.add(bk)
                    fresh.append((tag or "a window behind", list(r)))
                # what is left over: a window with no rectangle to measure -
                # one filling the screen, or the browser's strip along the
                # top - is kept as it was drawn
                for k, (tag_, box_) in enumerate(behinds):
                    if k in taken_k:
                        continue
                    wide = box_[2] - box_[0] >= 0.88 * Wf
                    tall = box_[3] - box_[1] >= 0.80 * Hf
                    strip = box_[2] - box_[0] >= 0.88 * Wf and \
                        box_[3] - box_[1] <= 0.20 * Hf
                    if (wide and tall) or strip:
                        fresh.append((tag_, box_))
                behinds = fresh
            behinds.sort(key=lambda hb: -(hb[1][2] - hb[1][0]) * (hb[1][3] - hb[1][1]))
            if barred:
                # the browser's tab strip runs along the very top of the
                # screen, above whatever window it stands behind. It is read
                # on the top rows of the window that spans that strip -- often
                # the full-screen backdrop, not a front window -- so a picture
                # where no front window reaches the top still has a browser to
                # draw: every state this stretch shows is asked for it, front
                # windows first, then the backdrop ones behind them.
                src = [(stx, sl) for stx, sl, _ in subjects] \
                    + [(own, own) for own in states if own not in sub_states]
                browser_bits = []
                for stx, sl in src:
                    strip = behind_for(sl, dict(s, size=s["size"]), stx)
                    if strip:
                        sb = strip[0][1]
                        # A WINDOW BEHIND THE STRIP BEGINS UNDER IT. The
                        # browser's tabs and address bar run across the top
                        # of the screen, and a window filling the screen
                        # behind them begins where they end - drawn from
                        # the desktop bar down, its outline stood over the
                        # strip that was plainly in front of it.
                        for k_, (tag_, box_) in enumerate(behinds):
                            if (box_[2] - box_[0] >= 0.88 * Wf and box_[1] < sb[3] - 0.01 * Hf
                                    and box_[3] > sb[3] + 0.2 * Hf):
                                behinds[k_] = (tag_, [box_[0], float(sb[3]), box_[2], box_[3]])
                        # THE BROWSER'S BOX IS THE BROWSER, NOT ITS CHROME.
                        # `sb` is the extent of the tab strip and address
                        # bar -- the only part of the browser standing clear
                        # of Obsidian -- and outlining THAT said the browser
                        # was a band 6% of the screen tall where it stood
                        # 97% tall. Its own rectangle can now be measured;
                        # the strip is only where its top edge is.
                        # The strip's own box runs from the top of the frame
                        # down to where its words end, so its TOP says
                        # nothing; what identifies the browser among the
                        # measured windows is that it is the one standing
                        # HIGHEST, with the strip inside its own top. A
                        # window that begins below the strip is something
                        # the strip is drawn over, not the window it
                        # belongs to.
                        tall = [b for b in frame_bigwins(s)
                                if (b[3] - b[1]) >= 0.5 * Hf and b[1] <= sb[3]]
                        bb = min(tall, key=lambda b: b[1]) if tall else None
                        behinds.append(("the browser, behind", list(bb) if bb else sb))
                        if bb:
                            browser_bits = browser_chrome(s, bb, sb[3])
                        break
            # A WINDOW DRAWN IN FULL MUST ITSELF BE A WINDOW. Its box has
            # to be one the frame drew, or - where the frame drew none,
            # because the window fills the screen - a box that fills the
            # screen or a strip across it. A box that is neither is a
            # patch of the screen, and filling it in says a window stood
            # there at a size it never had. Where that program is already
            # outlined in this picture, the outline is the honest drawing
            # and the patch goes.
            def is_window(b):
                if any(furnish._within(b, r) > 0.7 and furnish._within(r, b) > 0.7
                       for r in real_w):
                    return True
                wide = (b[2] - b[0]) >= 0.60 * Wf
                tall = (b[3] - b[1]) >= 0.60 * Hf
                strip = (b[2] - b[0]) >= 0.88 * Wf and (b[3] - b[1]) <= 0.20 * Hf
                return (wide and tall) or strip
            # A frame the screen drew no rectangle on is a window filling
            # it: either maximised, or the video zoomed inside one. Its
            # edges are the frame's own, less whatever strip stands across
            # the top - the browser's chrome over it. Drawn instead at the
            # spread of the panes it was read from, such a window comes out
            # a patch in the middle with its own tree standing outside it.
            if not real_w and subjects:
                big = max(subjects, key=lambda x: (x[2][2] - x[2][0]) * (x[2][3] - x[2][1])
                          if x[2] else 0)
                # A MEASURED BOX BEATS THE FRAME'S OWN EDGES. `shapes` closed
                # no rectangle here, but `bigwin` measures the windows the
                # screen cuts off, and the front window is one of them: the
                # topmost that some window behind has not already claimed.
                # Without this the front window was drawn from the desktop
                # bar down to the foot, less whatever SHORT strip stood
                # across the top -- and the moment the browser's outline
                # became its real box instead of its chrome strip, that
                # strip stopped being short, the subtraction stopped
                # happening, and this window was drawn 6% of the screen
                # taller than it stood.
                # THE SAME BOX, not merely a box of a like shape. Two
                # near-full-screen windows agree on three of their four
                # edges, so `furnish._close` -- which measures its slack as
                # a share of the smaller box -- calls them one window and
                # dropped the front one: 131 pixels apart at the top, on a
                # slack of 295. The question here is identity, so the
                # tolerance is a share of the FRAME.
                used = [b_ for _, b_ in behinds]
                free = [b for b in frame_bigwins(s)
                        if not any(abs(b[0] - u[0]) <= 0.01 * Wf
                                   and abs(b[1] - u[1]) <= 0.01 * Hf
                                   for u in used)]
                if free:
                    box0 = list(min(free, key=lambda b: b[1]))
                else:
                    top = 0.0
                    for tag_, b_ in behinds:
                        if b_[2] - b_[0] >= 0.88 * Wf and b_[3] - b_[1] <= 0.20 * Hf:
                            top = max(top, b_[3])
                    box0 = [0.0, top, float(Wf), float(Hf)]
                big[1].rect = box0
                subjects = [(x[0], x[1], box0 if x is big else x[2])
                            for x in subjects]
            fine = []
            _zoomed = bool(T and not flatT(T) and T[0] >= 1.15 and not barred)
            for stx, sl, shape in subjects:
                if shape and not is_window(shape) and id(stx) not in settled:
                    # a strip the crop cut off is judged after it is put back
                    # whole on the desktop, not by the sliver the frame showed
                    if _zoomed and (shape[0] <= 0.04 * Wf or shape[1] <= 0.04 * Hf
                                    or shape[2] >= 0.96 * Wf or shape[3] >= 0.96 * Hf):
                        fine.append((stx, sl, shape))
                        continue
                    app = label_for(stx, s["t0"]).split(":")[0].strip()
                    if any(t.split(":")[0].strip() == app
                           or app in t for t, _b in behinds):
                        continue          # already outlined, and honestly
                fine.append((stx, sl, shape))
            if fine:
                subjects = fine
            m_t0 = next((mm for mm in moments if mm["ts"] == s["t0"]), None)
            cam = shapes.camera_box(frame_of(m_t0)) if m_t0 else None
            cam_pic = None   # a camera picture is never pasted in; it is outlined
            head = f"### {s['t0']}" + ("" if s["t0"] == s["t1"] else f" to {s['t1']}") + \
                   " - " + " \u00b7 ".join(label_for(st) for st, _, _ in subjects)
            parts += [head, ""]
            for stx, sl, shape in subjects:
                sl._label = label_for(stx)
                # the bar under a window in a picture says what the bar under
                # that window's own card says: the stretch's own reading, with
                # its gaps filled and anything read in front of the root - a
                # neighbour's sidebar landing in the same row - dropped
                mine, whole = sl.main_table(), stx.main_table()
                if mine and mine.path and whole and whole.path:
                    mine.path = mend_path(mine.path, [whole.path])
                # the favorites sidebar, carried in when this Finder window
                # showed one this stretch but the reading missed it: its own
                # favorites words stand inside its rectangle NOW, so a sidebar
                # was on the screen there and only the reader's eye slid past
                if (stx.name == "The Finder window" and house_side and shape
                        and not furnish.side_words_of(sl)):
                    # ...AND THEY MUST STAND IN THE WINDOW'S LEFT MARGIN, which
                    # is where a sidebar is. Counted anywhere inside the
                    # rectangle, this found two "favorites" in the window at
                    # 00:01:00 that were nothing of the kind: the path bar's
                    # `Macintosh HD` and `Users` at x=1188 and x=888, and the
                    # Kind column's `Document` at x=2098 matching the favorite
                    # `Documents` by substring. That window was then drawn with
                    # a favorites sidebar it never showed - the one belonging to
                    # its neighbour, so the screen carried the same sidebar
                    # twice. The band between the window's own left edge and
                    # the left edge of its list is the only place a sidebar
                    # can be, and the neighbour's favorites at 00:01:00 sit
                    # far outside it.
                    _tp = next((q for q in sl.parts if q["fam"] == "table"
                                and q["model"] is sl.main_table()), None)
                    left = (_tp or {}).get("x0")
                    edge = left if left is not None else shape[2]
                    hits = 0
                    for t in s["ts"]:
                        for key, b in (words_of.get(t) or {}).items():
                            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                            if shape[0] <= cx <= min(edge, shape[2]) and shape[1] <= cy <= shape[3] \
                                    and any(hk in key or key in hk for hk in house_keys
                                            if len(key) >= 5):
                                hits += 1
                    if hits >= 2:
                        sl._carried_side = house_side
            # THE PICTURE IS THE WHOLE DESKTOP, EVEN WHERE THE VIDEO ZOOMED IN.
            # The editor zooms the recording in on a window now and then, so
            # the frame at those moments is a crop of the screen, enlarged.
            # Drawn as the frame showed it, the "desktop" picture then cut
            # windows off at its edges and moved the camera, and Tristan
            # read it as "almost like the whole screen is just zooming in
            # at specific points". His rule stands: the picture is the whole
            # screen. The fit already carries this stretch's frame onto the
            # base moment's places (`span_T`: a scale and a shift), so every
            # box here is taken back through it onto the desktop, the type
            # scale goes back to the screen's own, and the crop the video
            # showed is drawn as a dashed box that says so. A window the
            # crop cut off at the frame's edge runs on to where the window
            # really stood, known from the moments it stood clear.
            zoom_box = None
            # ...and only where the frame REALLY was a crop: a frame that
            # shows the desktop bar is the whole screen whatever the fit
            # says (the fit read 0.83 on two full-screen frames off a
            # handful of words), and a scale under one would mean the video
            # zoomed OUT past the screen, which no recording does.
            if T and not flatT(T) and T[0] >= 1.15 and not barred:
                _k = T[0]

                def _area(b_):
                    return max(0.0, b_[2] - b_[0]) * max(0.0, b_[3] - b_[1])

                def _cut_sides(b_):
                    """Which sides of a frame box the crop cut: left, top, right, bottom."""
                    return (b_[0] <= 0.04 * Wf, b_[1] <= 0.04 * Hf, b_[2] >= 0.96 * Wf, b_[3] >= 0.96 * Hf)

                def _whole_home(stx_, hbox_, cut_, sure_=True):
                    """The window this cut strip is part of: a same-program
                    window standing round it at this time whose sides AGREE
                    with the strip's on every side the crop did not cut.
                    Chosen by that agreement, not by size -- the smallest
                    box round the strip was a stray cluster whose right edge
                    sat 46 px inside the strip's own."""
                    # ...the window's own place among the candidates: at
                    # 00:04:00 the maximised Obsidian's own reading lost to
                    # a part-read cluster of another Obsidian state because
                    # only OTHER states were asked. Ties within 2% go to the
                    # larger box, since a cut strip belongs to the whole.
                    # EVERY PLACE THE WINDOW WAS READ, not the one nearest
                    # in time: nearest in time is this very moment's own
                    # part-reading, which is the strip being asked about.
                    # The maximised Obsidian read ten seconds later is the
                    # whole; it is a reading of the same window and is here.
                    best_, best_off = None, None
                    cands_ = []
                    for o_ in states:
                        if o_.name != stx_.name:
                            continue
                        hb_at = home_at(o_, s["t0"])
                        if hb_at:
                            cands_.append(hb_at)
                        cands_.extend(list(mem[1]) for mem in (home_reads.get(id(o_)) or ()) if mem[1])
                    if os.environ.get("SN_ZOOM"):
                        print("  whole? %s strip %s cands %s" % (stx_.name, [round(v) for v in hbox_],
                              [[round(v) for v in c_] for c_ in cands_]), file=sys.stderr)
                    for hb2 in cands_:
                        if not hb2 or furnish._within(hbox_, hb2) < 0.8 or _area(hb2) < 1.3 * _area(hbox_):
                            continue
                        if hb2[0] < -0.05 * Wf or hb2[1] < -0.05 * Hf or hb2[2] > 1.05 * Wf or hb2[3] > 1.05 * Hf:
                            continue                  # a box past the screen is a fit gone wrong
                        # A BOX DRAWN ROUND THE WORDS HAS NO EDGES TO AGREE ON.
                        # Where the strip's own edges were measured off the
                        # frame, the whole must agree on the sides the crop
                        # left; where they are only where the words sat, its
                        # left and top are inside the window, and the largest
                        # reading of the window that holds the strip is it.
                        if not sure_:
                            if best_ is None or _area(hb2) > _area(best_):
                                best_, best_off = hb2, 0.0
                            continue
                        off_ = 0.0
                        for i_, cut1 in enumerate(cut_):
                            if not cut1:
                                off_ += abs(hb2[i_] - hbox_[i_]) / (Wf if i_ % 2 == 0 else Hf)
                        if off_ > 0.12:
                            continue
                        if best_ is None or off_ < best_off - 0.02 or (abs(off_ - best_off) <= 0.02 and _area(hb2) > _area(best_)):
                            best_, best_off = hb2, off_
                    return best_

                def _home_box(b_, hb_=None):
                    x0_, y0_, x1_, y1_ = back(T, list(b_))
                    if hb_:
                        # a side the crop cut runs on to where the window
                        # really stood; the crop's edge sits a little inside
                        # the frame's own, so the test is a few percent
                        if b_[0] <= 0.04 * Wf and hb_[0] < x0_:
                            x0_ = hb_[0]
                        if b_[1] <= 0.04 * Hf and hb_[1] < y0_:
                            y0_ = hb_[1]
                        if b_[2] >= 0.96 * Wf and hb_[2] > x1_:
                            x1_ = hb_[2]
                        if b_[3] >= 0.96 * Hf and hb_[3] > y1_:
                            y1_ = hb_[3]
                    return [max(0.0, x0_), max(0.0, y0_), min(float(Wf), x1_), min(float(Hf), y1_)]

                def _whole_home_named(label_, hbox_, cut_):
                    """The same, for an outline that carries only a label."""
                    app_ = furnish._app_of(label_)
                    best_, best_off = None, None
                    for o_ in states:
                        if not app_ or furnish._app_of(o_.name) != app_:
                            continue
                        hb2 = home_at(o_, s["t0"])
                        if not hb2 or furnish._within(hbox_, hb2) < 0.8 or _area(hb2) < 1.3 * _area(hbox_):
                            continue
                        off_ = 0.0
                        for i_, cut1 in enumerate(cut_):
                            if not cut1:
                                off_ += abs(hb2[i_] - hbox_[i_]) / (Wf if i_ % 2 == 0 else Hf)
                        if off_ > 0.12:
                            continue
                        if best_ is None or off_ < best_off:
                            best_, best_off = hb2, off_
                    return best_

                _subj = []
                for stx, sl, shape in subjects:
                    if shape:
                        hb_ = home_at(stx, s["t0"])
                        raw_ = back(T, list(shape))
                        # a strip of a window the crop cut off is that window
                        cut_ = _cut_sides(shape)
                        sure_ = bool(getattr(sl, "_on_frame", False))
                        whole_ = _whole_home(stx, raw_, cut_, sure_) if any(cut_) else None
                        if whole_ is not None:
                            hb_ = whole_
                            # THE SAME PHYSICAL WINDOW UNDER ANOTHER NAME
                            # LENDS ITS SIDEBAR'S SHARE. The memory window
                            # is the jaredrhodenizer window navigated, and
                            # its sidebar was never on screen: the house's
                            # median share (24%) stood in where that window
                            # measures 28%. The Finder state whose own home
                            # box is this whole is that window.
                            if stx.name == "The Finder window" and getattr(sl, "_side_from_house", False):
                                for o_ in states:
                                    if o_ is stx or o_.name != stx.name:
                                        continue
                                    boxes_ = [home_at(o_, s["t0"])] + [list(mem[1]) for mem in (home_reads.get(id(o_)) or ()) if mem[1]]
                                    if any(b_ and all(abs(b_[i_] - whole_[i_]) <= 0.02 * (Wf if i_ % 2 == 0 else Hf) for i_ in range(4)) for b_ in boxes_):
                                        sib_ = furnish.side_share_card(o_)
                                        if sib_ and 0.1 <= sib_ <= 0.45:
                                            sl.side_share = sib_
                                            sl._side_from_house = False
                                            break
                        if os.environ.get("SN_ZOOM"):
                            print("  subject %s: frame %s -> home %s, whole %s" % (
                                label_for(stx, s["t0"]), [round(v) for v in shape],
                                [round(v) for v in raw_], hb_ and [round(v) for v in hb_]), file=sys.stderr)
                        # a box drawn round the words, cut by the crop, is the
                        # whole window it belongs to on every side
                        home_ = (list(whole_) if (whole_ is not None and not sure_)
                                 else _home_box(shape, hb_))
                        home_ = [max(0.0, home_[0]), max(0.0, home_[1]), min(float(Wf), home_[2]), min(float(Hf), home_[3])]
                        # the part of a Finder the crop cut off down its left
                        # side is its sidebar, by Finder's own layout; drawn
                        # whole, the window carries the favorites the video
                        # read on it, or the list spreads over ground the
                        # sidebar had and every column lands off its place
                        if (stx.name == "The Finder window" and house_side and cut_[0]
                                and home_[0] < raw_[0] - 0.15 * (home_[2] - home_[0])
                                and not furnish.side_words_of(sl)):
                            sl._carried_side = house_side
                            sl._cut_left = False
                        # the tree's column was measured against the FRAME
                        # box; against the whole window at home it is a
                        # smaller share (12% of the maximised Obsidian at
                        # 00:04:00, not the 32% of the strip the crop showed)
                        # ...set here whether or not the frame-space pass set
                        # it: left unset, the drawing fell back to the tree
                        # pane's FRAME edges against the HOME box (25% of the
                        # window for a tree that took 12%)
                        if home_[2] > home_[0]:
                            tr_ = None
                            for m_, g_ in getattr(stx, "pieces", ()):
                                if m_["ts"] not in s["ts"]:
                                    continue
                                for q_ in (g_.get("panes") or []):
                                    if q_.get("kind") == "a file tree" and q_.get("box"):
                                        b_ = back(T, list(q_["box"]))
                                        if tr_ is None or b_[2] > tr_[2]:
                                            tr_ = b_
                            if tr_ is not None and home_[0] <= tr_[2] <= home_[2]:
                                sl._tree_fr = max(4, round(100.0 * (tr_[2] - home_[0]) / (home_[2] - home_[0])))
                        shape = home_
                        sl.rect = shape
                    if getattr(sl, "_row_step", 0):
                        sl._row_step = sl._row_step / _k
                    _subj.append((stx, sl, shape))
                subjects = _subj
                # THE BROWSER'S STRIP IN A ZOOMED FRAME. The strip is sought
                # only where the desktop bar was seen, and a zoomed frame
                # never shows the bar, so at 00:04:00 the address bar read
                # above Obsidian's tree went unsought and the window carried
                # its raw reading's top -- the screen's edge, 190 px above
                # where the frame shows it under Chrome's bar. The strip is
                # sought among the subjects here; found, a window filling the
                # screen below it begins under it, as a window behind the
                # strip does, and the strip is drawn behind.
                if not any(t_ == "the browser, behind" for t_, _b in behinds):
                    for stx_, sl_, _shape_ in subjects:
                        strip_ = behind_for(sl_, dict(s, size=s["size"]), stx_)
                        if not strip_:
                            continue
                        sb_ = strip_[0][1]                      # the frame's own space
                        y1_ = back(T, list(sb_))[3]             # home
                        for i_, (stx2, sl2, shape2) in enumerate(subjects):
                            if (shape2[2] - shape2[0] >= 0.88 * Wf and shape2[1] < y1_ - 0.01 * Hf
                                    and shape2[3] > y1_ + 0.2 * Hf):
                                shape2 = [shape2[0], float(y1_), shape2[2], shape2[3]]
                                sl2.rect = shape2
                                subjects[i_] = (stx2, sl2, shape2)
                        behinds.append(("the browser, behind", [0.0, 0.0, float(Wf), float(sb_[3])]))
                        if not browser_bits:
                            browser_bits = browser_chrome(s, [0.0, 0.0, float(Wf), float(Hf)], sb_[3])
                        if os.environ.get("SN_ZOOM"):
                            print("  strip in the zoom: %s bottom %d -> home %d" % (stx_.name, sb_[3], y1_), file=sys.stderr)
                        break
                behinds = [(t_, _home_box(b_, _whole_home_named(t_, back(T, list(b_)), _cut_sides(b_))
                                          if any(_cut_sides(b_)) else None)) for t_, b_ in behinds]
                _ghosts = [(_home_box(b_) if b_ else b_, t_, k_) for b_, t_, k_ in ghost_list(s, sub_states, carded)]
                if cam:
                    cam = _home_box(cam)
                browser_bits = [(_home_box(cb_), tb_, ad_, rt_) for cb_, tb_, ad_, rt_ in (browser_bits or [])]
                # the crop itself is NOT clipped to the screen: a zoom that
                # ran past the desktop's edge shows a dark band there, and
                # cutting the box at the edge would shift every comparison
                # by that band's width (an eleventh of the crop at 00:04:00)
                zoom_box = back(T, [0.0, 0.0, float(Wf), float(Hf)])
                if os.environ.get("SN_ZOOM"):
                    print("ZOOM %s: k %.2f shift %.0f,%.0f -> crop %s" % (
                        s["t0"], T[0], T[1], T[2], [round(v) for v in zoom_box]), file=sys.stderr)
            else:
                _ghosts = ghost_list(s, sub_states, carded)
            _shot = (furnish.screen_shot(
                {"t0": s["t0"], "t1": s["t1"]},
                [(sl, shape) for _, sl, shape in subjects],
                s["size"][0], s["size"][1],
                bar_words if barred else None, clock if barred else "",
                behind_cards=behinds,
                zoom=zoom_box,
                # ONLY THE TOP LAYER GETS FULL CONTENT; EVERYTHING BEHIND IS
                # AN OUTLINE. Tristan's ruling, found in the record on
                # 2026-08-24: "those outlined screens NEED content within the
                # TOP most SHOWN with FULL READABILITY windows...only the top
                # layer gets full content, everything behind is an outline."
                # The desktop bar is the one exception, and it is drawn
                # separately. So the desktop picture lays down NO loose text
                # behind the front windows -- a window behind is its outline,
                # and its content lives in its own card below (view two).
                # `screen_ink` stays built for the day a never-carded window
                # (a browser strip) is drawn behind in the desktop view, but
                # it is not poured onto the picture as loose words.
                ink=(),
                # THE BROWSER'S CAUGHT CHROME IS NOT DRAWN YET, and this is
                # a declared limit rather than a silent omission. Tristan's
                # exception allows it -- a window that never stands clear
                # anywhere has no card of its own, so the desktop picture is
                # the only place its tabs and address bar can live -- and
                # `screen_shot` takes them. Drawn as it stands it costs
                # 0.03 of ink agreement at 00:00:00 and gains nothing, for
                # three reasons that are each their own piece of work: it
                # lands on the desktop bar's row instead of under it, its
                # type comes out at the page's scale rather than the strip's
                # own measured row height, and `furnish.browser_behind`
                # recovers two of the five tabs. The box is measured; the
                # chrome is not finished.
                chrome=(browser_bits if barred else ()),
                chrome_step=next((getattr(sl_, "_row_step", 0)
                                  for _, sl_, _ in subjects
                                  if getattr(sl_, "_row_step", 0)), 0.0),
                ghosts=_ghosts,
                camera=(cam, cam_pic) if cam else None,
                sure=all(any(t in st.measured for t in s["ts"]) or id(st) in settled
                         for st, _, _ in subjects),
                kz=(1.0 if zoom_box else (T[0] if T else 1.0))))
            parts.append(_shot)
            parts.append("")
            # A BROWSER READ AND NOT DRAWN SAYS SO. At 00:04:00 the frame is
            # panned past the desktop bar, so the whole chrome path is never
            # asked for (Run 19t), and the browser's address bar - read,
            # confirmed, and sitting in the frame's top strip - appears
            # nowhere. The picture then shows one window where the screen
            # held a browser above it, and looks confident about it.
            _addr = ""
            for _t in s["ts"]:
                _mm = next((x for x in moments if x["ts"] == _t), None)
                for _p in ((_mm or {}).get("panes") or []):
                    for _r in ((_p.get("data") or {}).get("remainder") or []):
                        if re.search(r"type a URL|https?://", str(_r.get("text") or "")):
                            _addr = str(_r["text"]).strip()
                    for _l in (_p.get("lines") or []):
                        if re.search(r"type a URL|https?://", str(_l)):
                            _addr = _addr or re.sub(r"^.*?\]\s*", "", str(_l)).strip()
            if _addr and "sn-browser" not in _shot:
                parts += ["*A browser stood above this window - its address bar reads "
                          "\u201c%s\u201d - and it is not drawn: the frame is panned past the desktop "
                          "bar, and its tabs were never read.*" % esc(_addr[:60]), ""]
            # WHAT THE RECORDING DID NOT CARRY, said UNDER the picture it
            # affects and not only on the front page. A picture showing one
            # window confidently where the screen held three reads as
            # unreliable; the same picture with a line saying the video
            # blacked that part of the screen out reads as honest. Tristan,
            # on the note as a whole: "at some points it looks greatd and at
            # other points in the same file where one looked great the other
            # doesn't keep the same quality". A note that is never wrong and
            # sometimes sparse reads as reliable; one that is sometimes
            # perfect and sometimes wrong reads as unreliable.
            _m0 = next((mm for mm in moments if mm["ts"] == s["t0"]), None)
            _hid = masked_share(frame_of(_m0)) if _m0 is not None else 0.0
            if _hid >= 0.05:
                if still:
                    parts += ["*The recording blacks out %.0f%% of this screen's height here. The windows "
                              "under those bands stood still from the moment before to the moment after, "
                              "and are drawn as they stood then; anything else behind the bands is not drawn, "
                              "because the video does not carry it.*" % (100 * _hid), ""]
                else:
                    parts += ["*The recording blacks out %.0f%% of this screen's height here. Any window "
                              "standing behind those bands is not drawn, because the video does not "
                              "carry it.*" % (100 * _hid), ""]
            # AND WHAT WAS LOOKED AT AND NOT READ, which is a different claim
            # from what was not there. Only a region carrying ink counts: most
            # of what the reader passes over is desktop with nothing on it, and
            # saying so of blank wallpaper would be noise on every picture.
            _gaps = gaps_of(_m0) if _m0 is not None else []
            _lost = [g for g in _gaps if g.unread]
            if _lost:
                _blank = len(_gaps) - len(_lost)
                parts += ["*%s of this screen, %s of it, %s looked at and could not be read, so nothing "
                          "is drawn there.%s*"
                          % ("One part" if len(_lost) == 1 else "%d parts" % len(_lost),
                             " and ".join("%.0f%%" % (100 * g.area) for g in _lost),
                             "was" if len(_lost) == 1 else "were",
                             (" Everything else the reader passed over was blank."
                              if _blank else "")), ""]
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
              "only say where each of these stood. One part per program; a window seen only in part, and the "
              "desktop's own bar, come last.", ""]
    def split_windows(sts):
        """Two windows of one program are two windows. Whatever else is
        uncertain, two states that stood on the screen at the SAME moment
        cannot be one window opened twice, so a program's states are dealt
        into as many windows as the clock demands: each state joins a window
        it never shared a moment with, the one it follows most closely, and
        starts a new one when there is none."""
        groups = []
        for st in sorted(sts, key=lambda s: s.times[0]):
            mine = set(st.times)
            free = [g for g in groups if not any(mine & set(o.times) for o in g)]
            if not free:
                groups.append([st])
                continue
            # A window walks up and down one tree, so the strongest sign that
            # this state continues that window is its path bar: consecutive
            # states of one window share a long run of ancestors, and two
            # windows opened on different folders do not. After that, a
            # window keeps its place when it is navigated; failing both, the
            # window that was on screen most recently.
            here = home_at(st, st.times[0])
            my_t = st.main_table()
            my_path = list(my_t.path) if my_t and my_t.path else []

            def fits(g):
                prev = max(g, key=lambda o: o.times[-1])
                pt = prev.main_table()
                its_path = list(pt.path) if pt and pt.path else []
                same = 0
                for a, b in zip(my_path, its_path):
                    if not crumb_same(a, b):
                        break
                    same += 1
                there = home_at(prev, prev.times[-1])
                share = 0.0
                if here and there:
                    w = min(here[2], there[2]) - max(here[0], there[0])
                    h = min(here[3], there[3]) - max(here[1], there[1])
                    if w > 0 and h > 0:
                        small = min((here[2] - here[0]) * (here[3] - here[1]),
                                    (there[2] - there[0]) * (there[3] - there[1]))
                        share = (w * h) / max(1.0, small)
                return (same, round(share, 2), prev.times[-1])

            max(free, key=fits).append(st)
        return groups

    # two windows of one program are two windows, and the note's first line
    # says so rather than counting a program's states as one window's history
    COUNT = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
             7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    for w in windows:
        k = len(split_windows([st for st in shown if st.name == w]))
        say = w[0].lower() + w[1:]
        if k > 1:                      # "the Finder window" -> "two Finder windows"
            bare = re.sub(r"^the ", "", say)
            say = f"{COUNT.get(k, k)} {bare}s"
        parts[head_at] = parts[head_at].replace(f"@@{w}@@", say)
    parts[head_at] = re.sub(r"(\w+ windows) \((\d+) states\)",
                            r"\1, \2 folder views between them", parts[head_at])

    for w in windows:
        groups = split_windows([st for st in shown if st.name == w])
        # one physical window's path bar, read whole at one moment and in
        # pieces at another: the pieces are filled in from the moment it
        # stood clear. This is mended within the physical window, across its
        # folder-views, because the path is the one thing they share.
        for sts in groups:
            tables = [t for st in sts for t in [st.main_table()] if t and t.path]
            for t in tables:
                t.path = mend_path(t.path, [o.path for o in tables if o is not t])
        # EACH FOLDER VIEW IS ITS OWN CARD. Tristan's rule: a new folder
        # opening in the same Finder window is a new window, not a state of
        # an old one - "two windows of the same app don't count as one
        # window, but two...same with if a one window changes to very
        # different content (new folder opens in same finder window)." So
        # every folder-view is a top-level card in the order it first
        # showed, never nested under a physical window as an "earlier
        # state" - which was the opposite of the rule, naming the physical
        # window as the thing and the folders as its history.
        # ONE PROPORTION PER WINDOW, NOT PER SECTION. A window's sections are
        # its folder views - the same window, so they must stand in the same
        # shape as each other, or a reader scrolling from one to the next
        # watches it change. The shape comes from the moments the reader
        # MEASURED that window, which are the moments it stood clear.
        shape_of = {}
        for g in groups:
            sure, any_ = [], []
            for o in g:
                for t_ in (getattr(o, "times", None) or []):
                    r_ = (getattr(o, "rects", None) or {}).get(t_)
                    if not r_ or r_[2] - r_[0] <= 0 or r_[3] - r_[1] <= 0:
                        continue
                    (sure if t_ in (getattr(o, "measured", None) or ()) else any_).append(r_)
            use = sure or any_
            if use:
                ws = sorted(r_[2] - r_[0] for r_ in use)
                hs = sorted(r_[3] - r_[1] for r_ in use)
                w_, h_ = ws[len(ws) // 2], hs[len(hs) // 2]
                if w_ > 0:
                    # THE SCREEN IT STOOD ON, not the page it is drawn on. A
                    # window that took a third of the desktop is drawn a third
                    # as wide as one that filled it, so two cards side by side
                    # carry their real difference in size. The floor of 0.35
                    # is there because these sections must stay readable: a
                    # sliver of a window is still a window someone has to read.
                    screen_w = max((mm.get("size") or [0])[0] for mm in moments) if moments else 0
                    for o in g:
                        shape_of[id(o)] = (h_ / w_,
                                           min(1.0, max(0.35, w_ / screen_w)) if screen_w else None)
        # A CARD THAT ADDS NOTHING IS NOT A VIEW OF THE WINDOW. One window can
        # end up with four cards where two of them are an empty frame around a
        # stray line -- measured on this video, the Obsidian window's second
        # card holds no tree, no list, and 25 words of which 100% already stand
        # in another of its cards, and the third holds four words. A reader
        # scrolls past two window frames that say nothing, which is the layout
        # reading as wrong even though every part of it is true.
        #
        # So a state with NO STRUCTURE OF ITS OWN -- no tree rows, no list rows
        # -- whose words are already carried by another card of the same
        # window is not drawn again. Its moments are added to the card that
        # does carry them, so nothing about WHEN the window stood that way is
        # lost. The test is containment against the other cards' own text, not
        # a size threshold: a small card holding something new is kept.
        def _card_words(st_):
            h = st_.window_html() or ""
            h = re.sub(r"&[a-z]+;|&#\d+;", " ", re.sub(r"<[^>]+>", " ", h))
            return set(x.lower() for x in re.findall(r"[A-Za-z][A-Za-z']{3,}", h))

        def _has_structure(st_):
            h = st_.window_html() or ""
            return ('<div class="sn-tree">' in h and "<div>" in h.split('<div class="sn-tree">')[1][:4000]) \
                or "<tr>" in h

        folded = {}
        for g in groups:
            if len(g) < 2:
                continue
            words = {id(o): _card_words(o) for o in g}
            for o in g:
                if _has_structure(o):
                    continue
                mine = words[id(o)]
                others = set().union(*[words[id(x)] for x in g if x is not o]) or set()
                # a word cut at the edge (`ther` for `there`) is carried by
                # the whole word another card holds
                carried = {w_ for w_ in mine if w_ in others
                           or (len(w_) >= 4 and any(x_.startswith(w_) for x_ in others))}
                if mine and (len(carried) == len(mine) or (len(mine) >= 8 and len(carried) >= 0.9 * len(mine))):
                    keep = max((x for x in g if x is not o), key=lambda x: len(words[id(x)]))
                    folded.setdefault(id(keep), []).extend(o.times)
                    folded[id(o)] = None
        # A WINDOW CUT OFF BY THE SCREEN'S EDGE IS THE WINDOW IT IS, not a
        # window of its own. From 00:01:50 the memory Finder stood pushed off
        # the left edge with only its Size and Kind columns in view and its
        # bar reading `…er-Documents-jarvis-demo › m…`; read without a Name
        # column it became a state of its own and a card of sixteen sizes.
        # Its bar names the folder whose card already stands - the same file
        # scrolled is the same card - so its moments join that card. Its
        # sixteen nameless rows are a stretch of the list never read whole
        # and cannot be placed among the named rows, so they are not drawn.
        def _cut_of(frag, whole):
            ft_, wt_ = frag.main_table(), whole.main_table()
            if not (ft_ and wt_ and wt_.path) or frag.title or not whole.title:
                return False
            if any(h and "Name" in h for h in ft_.header) or set(frag.times) & set(whole.times):
                return False
            reads = [w_ for p_ in (getattr(ft_, "paths", None) or []) for w_ in p_] + list(ft_.path or [])
            reads = [flat(w_).rstrip("›>") for w_ in reads if len(flat(w_)) >= 8]
            whole_flats = [flat(c_) for c_ in wt_.path]
            if reads and not all(any(wf == r_ or wf.endswith(r_) for wf in whole_flats) for r_ in reads):
                return False
            # the bar the window itself kept, or - read as loose words when
            # no bar closed - a word of its own that is the tail of one of
            # the folder's long crumbs (`er-Documents-jarvis-demo`)
            tails = [(flat(w_).rstrip("›>"), str(w_).rstrip().endswith((">", "\u203a")))
                     for w_ in frag.words() if len(flat(w_)) >= 8]
            if reads:
                return True
            for t_, cont in tails:
                for k_, wf in enumerate(whole_flats):
                    if len(wf) >= 12 and wf != t_ and wf.endswith(t_):
                        # `er-Documents-jarvis-demo >`: the chevron says the
                        # bar went on, so the folder on show sits UNDER this
                        # crumb - the window whose bar ends here is its parent
                        if cont and k_ == len(whole_flats) - 1:
                            continue
                        return True
            return False
        _all = [s_ for g in groups for s_ in g]
        for o in _all:
            if id(o) in folded and folded[id(o)] is None:
                continue
            whole = next((x for x in _all if x is not o and _cut_of(o, x)), None)
            if whole is not None:
                folded.setdefault(id(whole), []).extend(o.times)
                folded[id(o)] = None
        # THE SAME NOTE, READ FROM BEHIND THE FINDERS, IS THE SAME CARD. A
        # state named for this window because its words matched the
        # window's own note (`_same_as`, set where the rest-of-the-screen
        # states are named) is that note seen through a gap, never a card
        # of its own: its moments join the fullest card of the window.
        def _fullness(x_):
            d_, t_ = x_.main_doc(), x_.tree()
            return (len(d_.lines) if d_ else 0) + (len(t_.lines) if t_ else 0)
        for o in _all:
            if id(o) in folded and folded[id(o)] is None:
                continue
            if getattr(o, "_same_as", None) is None:
                continue
            kin = [x for x in _all if x is not o and x.name == o.name
                   and not (id(x) in folded and folded[id(x)] is None)]
            if not kin:
                continue
            base = max(kin + [o], key=_fullness)
            if base is o:
                continue
            folded.setdefault(id(base), []).extend(o.times + (folded.get(id(o)) or []))
            folded[id(o)] = None

        # THE WINDOW'S FIXED FURNITURE IS SHARED BY EVERY CARD OF IT. A Finder's
        # favorites sidebar does not come and go as the folder changes, and a
        # tree's column does not move when the note scrolls; what changes from
        # moment to moment is only how much of the window the screen showed.
        # Measured on this video: four of the left window's five cards drew
        # no sidebar at all, because at those moments the screen was zoomed
        # in past the window's left edge -- while its first card, read when
        # the window stood clear, drew the sidebar in full. Tristan's rule:
        # "the sidebar is bigger in one than the other, no sidebar at all"
        # is the fault, and the fix is the puzzle-piece rule applied to the
        # window's furniture -- what one moment hid, another moment showed.
        # So every card of one physical window carries the fullest sidebar
        # any of its cards read, at the share the window's widest measured
        # moment gave it; and every card of a window with a tree beside a
        # note takes its column split from the moment that window showed the
        # most of itself (the most tree rows and note lines together), with
        # the note's own line length measured at that same moment against
        # the pane it sat in, so the card is the window in the pictures,
        # only large enough to read and as tall as its gathered content.
        def _home_furniture(g):
            words, share = [], None
            for o in g:
                sw = furnish.side_words_of(o)
                if len(sw) > len(words):
                    words = list(sw)
                sh = furnish.side_share_card(o)
                if sh and (share is None or sh < share):
                    share = sh
            best, tree_fr, line_fr = -1, None, None
            for o in g:
                for m_, g_ in (getattr(o, "pieces", None) or ()):
                    rect = (getattr(o, "rects", None) or {}).get(m_.get("ts"))
                    if not rect or rect[2] - rect[0] <= 0:
                        continue
                    w_ = float(rect[2] - rect[0])
                    trees = [p_ for p_ in (g_.get("panes") or [])
                             if p_.get("kind") == "a file tree" and len(p_.get("box") or []) == 4
                             and rect[0] - 0.05 * w_ <= p_["box"][0] and p_["box"][2] <= rect[0] + 0.5 * w_]
                    docs = [p_ for p_ in (g_.get("panes") or [])
                            if p_.get("kind") == "an open document" and len(p_.get("box") or []) == 4
                            and p_["box"][2] - p_["box"][0] >= 0.25 * w_
                            and rect[0] - 0.02 * w_ <= p_["box"][0] and p_["box"][2] <= rect[2] + 0.02 * w_]
                    if not (trees and docs):
                        continue
                    tr = max(trees, key=lambda p_: len(p_.get("lines") or p_.get("rows") or []))
                    dc = max(docs, key=lambda p_: p_["box"][2] - p_["box"][0])
                    score = len(tr.get("lines") or tr.get("rows") or []) + len(dc.get("lines") or dc.get("rows") or [])
                    if score <= best:
                        continue
                    t_ = (tr["box"][2] - rect[0]) / w_
                    if not 0.04 <= t_ <= 0.5 or tr["box"][2] > dc["box"][0]:
                        continue
                    xs = [it["box"] for it in draw2.items_of(dc) if it["box"][2] - it["box"][0] > 20]
                    editor = float(rect[2] - tr["box"][2])
                    if len(xs) >= 3 and editor > 0:
                        span = max(b[2] for b in xs) - min(b[0] for b in xs)
                        l_ = span / editor
                        if 0.15 <= l_ <= 1.0:
                            best, tree_fr, line_fr = score, t_, l_
            for o in g:
                o._side_home = (words, share)
                if tree_fr:
                    o._card_tree = tree_fr
                    o._card_line = line_fr
        for g in groups:
            _home_furniture(g)
        # ONE PART PER PROGRAM. Tristan's rule for this section: "a subsection
        # per window type (obsidian windows, finder windows, fragmented not
        # full windows like browser fragment, top bar of the desktop, etc)".
        _prog = re.sub(r"^[Tt]he ", "", re.sub(r" window$", "", w))
        _k = len(groups)
        parts.append(f"### {_prog}: " + (f"{COUNT.get(_k, _k)} windows" if _k > 1 else "one window"))
        parts.append("")
        for st in sorted((s for g in groups for s in g), key=lambda s: s.times[0]):
            if id(st) in folded and folded[id(st)] is None:
                continue
            _extra = [t for t in (folded.get(id(st)) or []) if t not in st.times]
            _when = span_of(st)
            if _extra:
                _all = sorted(set(st.times) | set(_extra))
                _when = _all[0] if len(_all) == 1 else (
                    "%s and %s" % (_all[0], _all[1]) if len(_all) == 2
                    else "%s to %s" % (_all[0], _all[-1]))
            parts.append(f"#### {w} - as at {_when}" + (f", {st.title}" if st.title else ""))
            parts.append("")
            _sh = shape_of.get(id(st)) or (None, None)
            _html = st.window_html()
            parts.append(card_shot(_html, _sh[0], _sh[1], getattr(st, "_tree_min", None)))
            parts.append("")
            for ln in st.said_html():
                parts.append(ln)
                parts.append("")
            if st.fine_html():
                parts.append(st.fine_html())
                parts.append("")
            parts.append("---")
            parts.append("")
    # A WINDOW SEEN ONLY IN PART IS STILL A WINDOW. The browser stood behind
    # Obsidian for the whole video with only its tab strip and address bar in
    # view along the top of the frame; the pictures draw that strip where it
    # sat, and this card gathers it once, read across every moment, with a
    # plain line saying the rest of the window was never on show.
    _tops, _seen_top = [], set()
    for st in shown:
        for t in (getattr(st, "topwords", None) or []):
            k_ = (str(t[0]).strip().lower(), int(round(float(t[1]) / 40)))
            if k_ not in _seen_top:
                _seen_top.add(k_)
                _tops.append(t)

    class _TopOnly:
        """A stand-in carrying only the words read along the top of the frame."""
        topwords = ()
    _bro = _TopOnly()
    _bro.topwords = _tops
    strip = furnish.browser_behind(_bro) if _tops else ""
    if strip:
        dark = any(getattr(st, "theme", None) == "dark" for st in shown)
        parts += ["### The browser: seen only at its top", "",
                  f'<div class="sn-window sn-browser-card{" sn-dark" if dark else ""}">{strip}'
                  '<div class="sn-covered">Only its tab strip and address bar were ever in view; '
                  'the rest of this window stood behind the others the whole time.</div></div>',
                  "", "---", ""]
    # THE DESKTOP BAR, ONCE PER PROGRAM THAT SET IT. The bar along the top of
    # the screen belongs to the program at the front, so the video shows one
    # bar per program; each is drawn once with the clock as it read while
    # that bar stood, first reading to last.
    # ONE BAR PER PROGRAM, NOT PER READING. The same bar comes back read in
    # two pieces in the wrong order at one moment (`Window Help Obsidian
    # File Edit...`) and with a menu misread at another (`inserf`); those
    # are the one bar. Two readings are the same bar when most of their
    # words agree, and the fullest reading that puts the program's name
    # first stands for all of them.
    bars = []

    def _bare(w_):
        return w_[3:-4] if (w_.startswith("<i>") and w_.endswith("</i>")) else w_

    def _first_is_app(ws):
        first = _bare(ws[0])
        return first[:1].isupper() and not same_text(first, "File") and not same_text(first, "Window") \
            and not same_text(first, "Help") and not same_text(first, "Edit") and not same_text(first, "View")

    def _same_bar(a, b):
        # two bars naming different programs are two bars, however many
        # menus they share: File, Edit, View, Window and Help are on every
        # bar, and by those alone Obsidian's bar folded into Finder's
        if _first_is_app(a) and _first_is_app(b) and not same_text(_bare(a[0]), _bare(b[0])):
            return False
        hits = sum(1 for w_ in a if any(same_text(_bare(w_), _bare(x)) for x in b))
        return hits * 10 >= 6 * min(len(a), len(b))

    for m in moments:
        ws = tuple(bar_at.get(m["ts"]) or ())
        if len(ws) < 3:
            continue
        c = clock_at.get(m["ts"], "")
        hit = next((b for b in bars if _same_bar(ws, b[0])), None)
        if hit is None:
            bars.append([ws, c, c])
            continue
        hit[2] = c or hit[2]
        if (_first_is_app(ws) and not _first_is_app(hit[0])) or \
                (_first_is_app(ws) == _first_is_app(hit[0]) and
                 sum(1 for w_ in ws if not w_.startswith("<i>")) > sum(1 for w_ in hit[0] if not w_.startswith("<i>"))):
            hit[0] = ws
    if bars:
        parts += ["### The desktop bar", "",
                  "The menu bar along the top of the screen, as each program at the front set it, "
                  "with the clock as it read while that bar stood.", ""]
        for ws, c0, c1 in bars:
            def _word(w_, first):
                it = w_.startswith("<i>") and w_.endswith("</i>")
                t_ = esc(w_[3:-4] if it else w_)
                t_ = f"<b>{t_}</b>" if first else t_
                return f"<i>{t_}</i>" if it else t_
            menus = " &nbsp; ".join(_word(w_, i == 0) for i, w_ in enumerate(ws[:14]))
            clock = c0
            if c1 and c1 != c0:
                day = " ".join(c0.split()[:-1])
                tail = c1[len(day):].strip() if day and c1.startswith(day) else c1
                clock = f"{c0} to {tail}"
            parts += [f'<div class="sn-menubar"><span>{menus}</span>'
                      + (f'<span class="sn-right">{esc(clock)}</span>' if clock else "") + "</div>", ""]
        parts += ["---", ""]

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
