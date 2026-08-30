import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import note_reader as N
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for p in sys.argv[1:]:
    res, _ = eng(p)
    rapid = [t for _, t, _ in (res or [])]
    note = N.read_note(p)
    print(f"=== {os.path.basename(p)}   backed={note['backed']:.2f} "
          f"body_lines={N.body_lines(note['markdown'])}")
    print("  what the fallback prints today (RapidOCR):")
    for t in rapid[:6]:
        print(f"      {t[:100]}")
    print("  what the document reader already has (tesseract, reconciled):")
    for r in note["rows"][:6]:
        print(f"      [{r.get('read_status','?'):>16}] {r['text'][:96]}")
