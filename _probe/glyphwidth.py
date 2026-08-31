"""Is a falling-glyph animation separable from a terminal by box SHAPE?

An interface's text boxes are words and lines; a rain of single characters is
one glyph per box. Measures, per frame, the median box width as a share of the
frame and the median characters per box.
"""
import os, sys, json
import cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import screenness as sc
from rapidocr_onnxruntime import RapidOCR

TRUTH = json.load(open("_probe/screen_truth.json"))
eng = RapidOCR()
out = []
for d, fs in sorted(TRUTH.items()):
    for fn, want in sorted(fs.items()):
        p = os.path.join("_probe/scratch/set", d, fn)
        work = sc.to_working_size(cv2.imread(p))
        W = work.shape[1]
        ws, cs = [], []
        for n, r0, r1, c0, c1 in sc.clusters(sc.cell_scores(work) >= sc.CELL_IS_SCREEN):
            h, w = work.shape[:2]
            rows, cols = sc.GRID
            y0, y1 = r0 * h // rows, (r1 + 1) * h // rows
            x0, x1 = c0 * w // cols, (c1 + 1) * w // cols
            crop = work[max(0, y0 - 8):min(h, y1 + 8), max(0, x0 - 8):min(w, x1 + 8)]
            if crop.size == 0 or min(crop.shape[:2]) < 24:
                continue
            sc_ = max(1, int(900 / max(1, crop.shape[1])))
            if sc_ > 1:
                crop = cv2.resize(crop, (crop.shape[1] * sc_, crop.shape[0] * sc_),
                                  interpolation=cv2.INTER_LANCZOS4)
            res, _ = eng(crop)
            for b, txt, _conf in (res or []):
                ws.append((max(pt[0] for pt in b) - min(pt[0] for pt in b)) / (crop.shape[1]))
                cs.append(len(txt.strip()))
        out.append({"vid": d, "f": fn, "want": want, "n": len(ws),
                    "w": float(np.median(ws)) if ws else 0.0,
                    "c": float(np.median(cs)) if cs else 0.0})
        print("%-24s %-12s %-6s %3d boxes  width %.3f  chars %.1f"
              % (d[:24], fn, want, len(ws), out[-1]["w"], out[-1]["c"]), flush=True)
json.dump(out, open("_probe/glyphwidth.json", "w"), indent=1)
