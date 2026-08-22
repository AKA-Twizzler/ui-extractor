import tree_reader, machine
p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-04-10_pane0.png")
rows = tree_reader.ocr_rows(p)
print(len(rows), "rows")
for r in rows:
    print(f'{r["y0"]:5d} {r["x0"]:5d}-{r["x1"]:5d} {r["name"][:40]!r}')
kept = tree_reader.tree_rows(rows)
print("kept", len(kept), [r["y0"] for r in kept][:5], "...", [r["y0"] for r in kept][-3:])
