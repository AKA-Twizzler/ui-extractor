"""Find a real stored pane that reads as loose text AND carries a reading
at twice the pane's median glyph height -- the specimen for the LARGE
stage."""
import glob
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"G:\AI\Ethereal\ui-extractor")
import pipeline
from rapidocr_onnxruntime import RapidOCR

DIRS = glob.glob(r"G:\Images\*")
eng = RapidOCR()
hits = 0
for d in sorted(DIRS):
    if "\\_" in d or d.endswith(".png") or d.endswith(".jpg"):
        continue
    for path in sorted(glob.glob(d + r"\*_pane*.png")):
        if "_3x" in path or "_tess" in path:
            continue
        res, _ = eng(path)
        if not res or len(res) < 4:
            continue
        hs = [max(p[1] for p in b) - min(p[1] for p in b) for b, _, _ in res]
        med = sorted(hs)[len(hs) // 2]
        if not med or max(hs) < 2.0 * med:
            continue
        rec = pipeline.say_pane(path, 0, eng)
        if rec is None:
            continue
        big = [ln for ln in rec.get("lines", [])
               if ln.startswith("[drawn large] ")]
        print(f"{path}  kind={rec['kind']!r}  "
              f"big={big[0][:80] if big else '-'}")
        hits += 1
        if hits >= 12:
            break
    if hits >= 12:
        break
print(f"{hits} candidates")
print("PROBE-DONE")
