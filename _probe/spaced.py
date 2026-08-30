import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verify_names as V
from rapidocr_onnxruntime import RapidOCR
eng = RapidOCR()
for p in sys.argv[1:]:
    res, _ = eng(p)
    texts = [t for _, t, _ in (res or [])]
    print(f"=== {os.path.basename(p)}")
    for (out, ok), raw in zip(V.confirm_readings(p, texts[:16]), texts[:16]):
        mark = "  " if ok else " ?"
        change = "  <-- respaced" if out != raw else ""
        print(f"  {mark} {out[:92]}{change}")
