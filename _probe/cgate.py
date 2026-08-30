import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import console_reader as cr
for p in sys.argv[1:]:
    r = cr.read_console(p)
    n = os.path.basename(p)
    if not r.get("is_console"):
        print(f"{n:34s} REFUSED  {r.get('why')}")
    else:
        marked = [l for l in r["lines"] if l.get("unsettled")]
        print(f"{n:34s} terminal, {len(r['lines'])} lines, "
              f"{len(marked)} marked unsettled")
        for l in marked:
            print(f"      {l['text'][:44]!r}  vs  {l['second'][:44]!r}")
