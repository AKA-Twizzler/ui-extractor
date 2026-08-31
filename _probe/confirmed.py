"""How much of the frame is interface AFTER the reading confirms it?

candidate_regions proposes from pixels and over-proposes on a dark room.
ui_regions then reads each proposal and keeps only the ones carrying aligned
text. This measures what survives -- the number the skim never kept.
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
        bgr = cv2.imread(p)
        cands = sc.candidate_regions(bgr)
        regions = sc.ui_regions(bgr, eng)
        out.append({"vid": d, "f": fn, "want": want,
                    "guess": float(sum(c["share"] for c in cands)),
                    "sure": float(sum(r["share"] for r in regions)),
                    "n": len(regions),
                    "boxes": int(max([r["boxes"] for r in regions], default=0))})
        print("%-24s %-12s %-6s guess %5.2f  sure %5.2f  %d region(s) %d boxes"
              % (d[:24], fn, want, out[-1]["guess"], out[-1]["sure"],
                 out[-1]["n"], out[-1]["boxes"]), flush=True)
json.dump(out, open("_probe/confirmed.json", "w"), indent=1)
print("\n%-8s %-24s %-24s" % ("", "guessed p10/p50/p90", "confirmed p10/p50/p90"))
for want in ("screen", "camera"):
    v = [r for r in out if r["want"] == want]
    print("%-8s %-24s %-24s" % (want,
          "%.2f %.2f %.2f" % tuple(np.percentile([r["guess"] for r in v], [10, 50, 90])),
          "%.2f %.2f %.2f" % tuple(np.percentile([r["sure"] for r in v], [10, 50, 90]))))
