import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import note_reader as N
for p in sys.argv[1:]:
    n = N.read_note(p)
    md = n["markdown"]
    print(f"{os.path.basename(p)}: body_lines={N.body_lines(md)} "
          f"backed={n['backed']:.2f} (needs >= {N.BACKED:.2f})  "
          f"rows={len(n['rows'])}")
    for r in n["rows"]:
        print(f"    [{r.get('read_status','?'):>16}] {r['text'][:78]}")
