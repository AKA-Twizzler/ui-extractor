"""Score a pf_run output (JSON lines) against truth.json: rows right, cells right, and every miss named."""
import sys, json, os
here = os.path.dirname(os.path.abspath(__file__))
truth = json.load(open(os.path.join(here, "truth.json")))
lines = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.startswith("{")]
tot_rows = tot_ok = tot_cells = cells_ok = 0; misses = []
for pane, got in zip(truth["panes"], lines):
    rows = got["rows"]; want = pane["rows"]
    for i, w in enumerate(want):
        tot_rows += 1; tot_cells += 4
        g = rows[i]["cells"] if i < len(rows) else []
        g = (g + ["", "", "", ""])[:4]
        ok = [a == b for a, b in zip(g, w)]
        cells_ok += sum(ok)
        if all(ok):
            tot_ok += 1
        else:
            misses.append("%s row %2d: %s" % (pane["frame"], i + 1, " | ".join(("%r!=%r" % (a, b)) for a, b, k in zip(g, w, ok) if not k)))
    if len(rows) != len(want):
        misses.append("%s: %d rows read, %d expected" % (pane["frame"], len(rows), len(want)))
print("rows right: %d of %d   cells right: %d of %d   secs: %s" % (tot_ok, tot_rows, cells_ok, tot_cells, [l.get("secs") for l in lines]))
for m in misses: print("  ", m)
