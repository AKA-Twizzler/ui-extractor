#!/usr/bin/env python3
"""Every row the reader read, drawn -- the fourth gate.

    python3 verify_rows.py <note.md> <records.jsonl> [--prove]

WHY THIS EXISTS. `compare.py` measures ink and cannot tell a dropped row from
a row drawn a pixel off. `verify_pictures.py` checks WINDOWS, not their
contents. So a list could quietly lose a line and every gate would pass it:
the `vault-demo` list dropped its `.obsidian` row in three pictures and
nothing but a person's eye noticed, because `strip_furniture` folded the
FOLDER `.obsidian` onto the menu bar's own `Obsidian` and deleted it as
furniture.

WHAT IT ASKS, and it asks it of one exact table at a time. For each pane the
reader read as a list or a tree, find the drawn table that carries most of
that pane's names, and report any name the reader read that the table does
not carry. Names are compared with two letters of slack, since the two
engines spell a cut-short name differently.

WHAT IT CANNOT SEE, declared rather than implied:
  - windows: a picture can pass this and still miss a whole window, or invent
    one. That is `verify_pictures.py`.
  - scale and placement: a row drawn at the wrong size, or in the wrong
    window, passes here. That is the side-by-side.
  - invention: a row drawn that nobody read is NOT reported. This gate is one
    way round only, by construction - it holds the drawing to the reading,
    and the reading is not the frame.
  - anything the reader never read. A gap in the reading is invisible here.

Exit 1 if any picture drops a row, so a run can gate on it.
"""
import json
import re
import sys
import unicodedata

SLACK = 2          # letters two engines may disagree on in one name


def norm(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", str(s)).lower())


def close(a, b):
    """Two readings of one name. A short name must match outright; a longer
    one may differ by up to `SLACK` letters, or be the other cut short."""
    if a == b:
        return True
    if len(a) >= 4 and (a in b or b in a):
        return True
    if abs(len(a) - len(b)) > 3 or min(len(a), len(b)) < 4:
        return False
    return sum(1 for x, y in zip(a, b) if x == y) >= max(len(a), len(b)) - SLACK


def panes_of(records):
    """Each moment's panes, each as the list of names the reader read in it."""
    out = {}
    for line in open(records, encoding="utf-8"):
        r = json.loads(line)
        ts = r.get("ts")
        if not ts:
            continue
        got = []
        for p in (r.get("panes") or []):
            names = [str(row[0]) for blk in ((p.get("data") or {}).get("blocks") or [])
                     for row in (blk.get("rows") or []) if row and row[0]]
            if not names:
                # a pane read as a TREE keeps its names in `lines`
                for l in (p.get("lines") or []):
                    l = str(l)
                    if l.startswith("[") or "|" in l:
                        continue
                    nm = l.strip("\u2502 \u02c3\u02c5\u25b8\u25be>").strip()
                    if nm and len(nm) < 60:
                        names.append(nm)
            names = [n for n in names if norm(n)]
            if len(names) >= 3:
                got.append(names)
        out[ts] = got
    return out


def tables_of(note_text):
    """Each picture's drawn tables, each as its column of names."""
    out = {}
    for m in re.finditer(r"### (\d\d:\d\d:\d\d)", note_text):
        ts = m.group(1)
        j = note_text.find("\n### ", m.end())
        sec = note_text[m.end(): j if j > 0 else len(note_text)]
        tabs = []
        for tab in re.findall(r"<table.*?</table>", sec, re.S):
            names = []
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tab, re.S):
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
                if cells:
                    n = norm(re.sub(r"<[^>]+>", "", cells[0]))
                    if n:
                        names.append(n)
            if names:
                tabs.append(names)
        # a Finder drawn from its names alone is a list too
        lis = [norm(re.sub(r"<[^>]+>", "", x))
               for x in re.findall(r'<span class="sn-litext">(.*?)</span>', sec, re.S)]
        lis = [x for x in lis if x]
        if lis:
            tabs.append(lis)
        out[ts] = tabs
    return out


def check(note_path, records_path, quiet=False):
    text = open(note_path, encoding="utf-8").read()
    panes, tables = panes_of(records_path), tables_of(text)
    dropped = {}
    for ts, tabs in sorted(tables.items()):
        for pane in panes.get(ts, []):
            keys = [(o, norm(o)) for o in pane]
            if not tabs:
                continue
            best = max(tabs, key=lambda tb: sum(1 for _o, n in keys if any(close(n, d) for d in tb)))
            hit = sum(1 for _o, n in keys if any(close(n, d) for d in best))
            if hit < max(3, 0.6 * len(keys)):
                continue          # not this window's list at all
            miss = [o for o, n in keys if not any(close(n, d) for d in best)]
            if miss:
                dropped.setdefault(ts, []).extend(miss)
    if not quiet:
        for ts in sorted(dropped):
            print("  %s  drops %d: %s" % (ts, len(dropped[ts]), ", ".join(dropped[ts][:6])))
        n = sum(len(v) for v in dropped.values())
        print("\nEVERY ROW THE READER READ IS DRAWN." if not dropped
              else "\n%d row(s) read and not drawn, over %d picture(s)." % (n, len(dropped)))
        print("NOT checked here (declared, not passed): whole windows, scale and placement,\n"
              "invented rows, and anything the reader never read.")
    return dropped


def prove(note_path, records_path):
    """A check never seen to fail is not a check. Delete a row from a real
    picture and require this gate to catch exactly that."""
    text = open(note_path, encoding="utf-8").read()
    m = re.search(r"(<tr[^>]*>(?:(?!</tr>).)*?</tr>)", text, re.S)
    broken = None
    for row in re.findall(r"<tr[^>]*>.*?</tr>", text, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        if cells and len(norm(re.sub(r"<[^>]+>", "", cells[0]))) >= 8 and "sn-head" not in row:
            broken = row
            break
    if broken is None:
        print("PROOF INCONCLUSIVE: no row long enough to remove.")
        return 1
    hurt = note_path + ".broken"
    open(hurt, "w", encoding="utf-8").write(text.replace(broken, "", 1))
    name = re.sub(r"<[^>]+>", "", re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", broken, re.S)[0]).strip()
    before, after = check(note_path, records_path, quiet=True), check(hurt, records_path, quiet=True)
    got = sum(len(v) for v in after.values()) > sum(len(v) for v in before.values())
    print("removed the row %r from a real picture" % name[:40])
    print("the gate SAW it." if got else "THE GATE DID NOT SEE IT -- this check is not a check.")
    import os
    os.remove(hurt)
    return 0 if got else 1


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    note, records = sys.argv[1], sys.argv[2]
    if "--prove" in sys.argv:
        return prove(note, records)
    return 1 if check(note, records) else 0


if __name__ == "__main__":
    raise SystemExit(main())
