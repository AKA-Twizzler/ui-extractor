import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2, checks, note_reader
for key, stamp in (("obsidian", "00:07:30"),):
    for p in checks.regions(key, stamp):
        got = note_reader.read_note(p)
        props = [k for k, _ in (got.get("properties") or [])]
        print(f"{os.path.basename(p):28s} lines {len(got.get('rows') or []):3d} "
              f"backed {got.get('backed', 0):.2f}  props {props}")
