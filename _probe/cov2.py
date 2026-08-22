import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import note_reader
D = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images"
note = note_reader.read_note(os.path.join(D, "00-04-10_pane2.png"))
for r in note["rows"]:
    print(f"{r.get('read_status','?'):12} xh={r.get('xh')} h={r.get('height_ratio')} | {r['text'][:70]!r} | second={str(r.get('text_second'))[:60]!r}")
