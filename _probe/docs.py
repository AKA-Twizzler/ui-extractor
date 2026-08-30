"""How much of a 'document' did the second engine confirm?

note_reader already reads every line twice and files the result under
read_status. Nothing has ever looked at it.
"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import note_reader

for png in sys.argv[1:]:
    got = note_reader.read_note(png)
    rows = got.get("rows") or []
    if not rows:
        print(f"{os.path.basename(png):34s} nothing read"); continue
    tally = collections.Counter(r.get("read_status", "none") for r in rows)
    good = sum(n for s, n in tally.items()
               if s in ("confident", "reconciled", "ambiguous-symbol",
                        "ambiguous-glyph"))
    print(f"{os.path.basename(png):34s} lines {len(rows):3d}  "
          f"backed {good}/{len(rows)} = {good/len(rows):.2f}  {dict(tally)}")
