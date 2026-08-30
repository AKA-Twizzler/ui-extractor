import sys, statistics
sys.path.insert(0, r"G:\\AI\\Ethereal\\ui-extractor")
import numpy as np, tree_reader as T, checks
def look(name, png):
    t = T.read_tree(png)
    rows = t["rows"] or []
    cols = t.get("guide_columns") or []
    cstep = statistics.median([b-a for a,b in zip(cols,cols[1:])]) if len(cols)>=2 else 0
    print(f"--- {name}")
    print(f"    verdict: {t.get(chr(39)+chr(39)) if False else t.get(str(chr(108))+str(chr(97))+str(chr(121))+str(chr(111))+str(chr(117))+str(chr(116))+str(chr(95))+str(chr(118))+str(chr(101))+str(chr(114))+str(chr(100))+str(chr(105))+str(chr(99))+str(chr(116)))}")
    print(f"    guide columns {cols}  step {cstep:.1f}  pitch {t.get(str(chr(114))+chr(111)+chr(119)+chr(95)+chr(112)+chr(105)+chr(116)+chr(99)+chr(104)):.1f}")
    if not rows:
        print("    no rows"); return
    x = np.array([r["x0"] for r in rows], float)
    d = np.array([r["depth"] for r in rows], float)
    h = statistics.median([r["y1"]-r["y0"] for r in rows]) or 1.0
    if d.max() > d.min():
        A = np.vstack([d, np.ones(len(d))]).T
        (step, base), *_ = np.linalg.lstsq(A, x, rcond=None)
    else:
        step, base = 0.0, x.mean()
    print(f"    rows {len(rows)}  depths {[int(v) for v in d]}")
    print(f"    name x0 {[int(v) for v in x]}")
    print(f"    row height {h:.1f}   fitted indent step through the NAMES {step:.1f}px")
    print(f"    that step as a share of a row height: {step/h:.2f}")
    print(f"    indent_miss {T.indent_miss(rows):.2f}")
    print(T.render(t))
    print()
look("Finder sidebar (wrong: invented nesting)", r"G:\\Images\\How To Make A Jarvis\\00-00-49_pane0.png")
look("the Obsidian fixture (a real tree)", checks.regions("obsidian", "00:02:09")[0])
