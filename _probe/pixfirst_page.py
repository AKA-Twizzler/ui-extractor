"""The memory card two ways, side by side: build 85's (from the reference
note) and the pixels-first one (from merged.json), in the same markup, so
the difference is the rows and nothing else. Writes compare.md (the two
cards under headings) and a bare HTML for the renderer.
    python3 _probe/pixfirst_page.py <reference_note.md> <merged.json> <out_dir>
"""
import html, json, os, re, sys

def card_of(note_text, heading_start):
    i = note_text.index(heading_start)
    j = note_text.index("\n#### ", i + 10) if "\n#### " in note_text[i + 10:] else len(note_text)
    block = note_text[i:j]
    m = re.search(r'<div class="sn-window sn-finder[^"]*"[^>]*>.*?</table>.*?</div></div></div></div>', block, re.S)
    return m.group(0) if m else None

def rows_html(rows):
    out = []
    for r in rows:
        cls = ' class="sn-selected sn-band-green"' if r["selected"] else ""
        ico = {"folder": '<span class="sn-tri">›</span><span class="sn-ico"></span>',
               "md": '<span class="sn-tri"></span><span class="sn-ico file md"></span>',
               "file": '<span class="sn-tri"></span><span class="sn-ico file"></span>'}.get(r["icon"], '<span class="sn-tri"></span><span class="sn-ico unknown"></span>')
        cells = list(r["cells"]) + [""] * (4 - len(r["cells"]))
        out.append("<tr%s><td>%s%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            cls, ico, html.escape(cells[0]), html.escape(cells[1]), html.escape(cells[2]), html.escape(cells[3])))
    return "".join(out)

if __name__ == "__main__":
    ref, merged_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
    note = open(ref, encoding="utf-8").read()
    old = card_of(note, "#### The Finder window - as at 00:01:20 to 00:03:00, memory")
    assert old, "the memory card was not found in the reference note"
    merged = json.load(open(merged_p, encoding="utf-8"))
    # the new card: the old card's furniture with the rows replaced
    m = re.search(r'(<table class="sn-list[^"]*">(?:<colgroup>.*?</colgroup>)?<tr class="sn-head">.*?</tr>)(.*?)(<tr class="sn-empty">.*?)(</table>)', old, re.S)
    assert m, "the table was not found in the card"
    new = old[:m.start()] + m.group(1) + rows_html(merged) + m.group(3) + m.group(4) + old[m.end():]
    os.makedirs(out, exist_ok=True)
    body = ("#### The memory window, build 85 (the reference)\n\n" + old + "\n\n"
            "#### The memory window, read pixels first\n\n" + new + "\n")
    open(os.path.join(out, "compare.md"), "w", encoding="utf-8").write(body)
    open(os.path.join(out, "new-card.html"), "w", encoding="utf-8").write(new)
    old_rows = re.findall(r"<tr(?: class=\"sn-selected[^\"]*\")?><td>.*?</tr>", m.group(2), re.S)
    print("old rows", len(old_rows), "new rows", len(merged))
    print("old empty cells:", sum(1 for r in old_rows for c in re.findall(r"<td>(.*?)</td>", r)[1:] if not c.strip()),
          "| new empty cells:", sum(1 for r in merged for c in r["cells"][1:] if not c.strip()))
    print("old dotted names:", sum(1 for r in old_rows if "..." in re.findall(r"<td>(.*?)</td>", r)[0] or ".." in re.findall(r"<td>(.*?)</td>", r)[0]),
          "| new dotted names:", sum(1 for r in merged if ".." in r["name"]))
    print("old nameless:", sum(1 for r in old_rows if re.sub(r"<[^>]+>", "", re.findall(r"<td>(.*?)</td>", r)[0]).strip() == ""),
          "| new nameless:", sum(1 for r in merged if not r["name"].strip()))
