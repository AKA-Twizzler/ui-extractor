import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import tree_reader, machine
p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-04-10_pane0.png")
rows = tree_reader.ocr_rows(p)
orig = tree_reader.grow_lattice
def spy(rows, chain, pitch):
    ys = [r["y0"] for r in rows]
    print("chain", len(chain), ys[chain[0]], ys[chain[-1]], "pitch", pitch)
    out = orig(rows, chain, pitch)
    print("grown", len(out), ys[out[0]], ys[out[-1]])
    return out
tree_reader.grow_lattice = spy
kept = tree_reader.tree_rows(rows)
print("kept", len(kept))
