"""How much of a table did the second engine back?"""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import columns
for png in sys.argv[1:]:
    got = columns.read_list(png)
    if not got.get("is_list"):
        print(f"{os.path.basename(png):30s} NOT A LIST - {got.get('why')}")
        continue
    for bi, b in enumerate(got["blocks"]):
        cells = [c for r in ([b["header"]] + b["rows"]) for c in r]
        flags = [f for r in ([b["headflags"]] + b["flags"]) for f in r]
        bad = sum(1 for f in flags if f)
        print(f"{os.path.basename(png):30s} block{bi} {b['columns']}col "
              f"{len(b['rows'])+1}rows  flagged {bad}/{len(flags)}  "
              f"head={b['header']}")
