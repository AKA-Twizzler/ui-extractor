import sys; sys.path.insert(0, r"/home/trism/.claude/jobs/014c964f/tmp/replay")
import note_reader, machine, statistics
p = machine.here("/mnt/g/Images/Move Memory Files Out of Claude Code Into Obsidian/Images/00-04-10_pane2.png")
orig = note_reader.clip_to_column
def spy(rows, right):
    print("right edge", right)
    for r in rows:
        words = r.get("words") or []
        if any(w[1] > right for w in words):
            print(r.get("read_status"), repr(r["text"][:60]), [(w[0], w[1], w[2]) for w in words][:12])
    return orig(rows, right)
note_reader.clip_to_column = spy
note = note_reader.read_note(p)
