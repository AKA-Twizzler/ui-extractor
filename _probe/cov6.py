import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import note_reader, machine
p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-03-00_pane0.png")
note = note_reader.read_note(p)
print("backed", round(note["backed"], 3), "rows", len(note["rows"]))
for r in note["rows"]:
    print(f'{r.get("read_status","?"):17s} {r.get("all_chars",0):4d} {r["text"][:70]!r}')
    if r.get("read_status") in ("uncertain",):
        print(f'{"":17s}      2nd: {r.get("text_second","")[:70]!r}')
