import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sweep
for p in ("_probe/july6new.txt", "_probe/memory.txt", "_probe/beginners.txt",
          "_probe/skills.txt", "_probe/stjudenew.txt"):
    if not os.path.exists(p):
        print(f"-- {p} missing"); continue
    bad = sweep.smells(open(p, encoding="utf-8", errors="replace").read())
    print(f"\n== {p}: {len(bad)} smells")
    for k, d in bad[:6]:
        print(f"     {k:<14} {d}")
