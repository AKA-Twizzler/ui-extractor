import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import draw3, old
header, moments, footer = old.load(sys.argv[1])
at_idx = {m["ts"]: i for i, m in enumerate(moments)}
print("idx", {k: v for k, v in at_idx.items() if k >= "00:02:50"})
states = draw3.build_states(moments)
draw3.harmonise(states)
for st in states:
    if st.name == "The Finder window" and not st.title:
        print("untitled finder:", sorted(st.measured), "rects:", {t: [round(v) for v in r] for t, r in st.rects.items()}, "seen:", sorted(st.seen) if hasattr(st, "seen") else None)
