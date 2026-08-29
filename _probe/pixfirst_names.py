"""The names read again with both engines, from the cached geometry: for
every full row of every frame, the Name cell read by RapidOCR (three and
two times its size) and by Tesseract (four times, one line), and the
reading kept is the one with the most underscores, then the longest once
folded (a dropped letter or underscore is the engines' common failure, an
added one is rare). Rewrites each frame's JSON in place with `name_alt`.
    python _probe/pixfirst_names.py <frames_dir_unc> <out_dir>
"""
import glob, json, os, re, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfirst

def fold(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def best(readings):
    readings = [r for r in readings if r]
    if not readings:
        return ""
    return max(readings, key=lambda r: (r.count("_"), len(fold(r)), r.count(".")))

if __name__ == "__main__":
    fdir, out = sys.argv[1], sys.argv[2]
    frames = {os.path.splitext(os.path.basename(f))[0]: f for f in glob.glob(os.path.join(fdir, "*.png"))}
    for s in ("20", "30", "40"):
        frames["00-01-" + s] = r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-01-%s.png" % s
    n = 0
    for jp in sorted(glob.glob(os.path.join(out, "*.json"))):
        stem = os.path.splitext(os.path.basename(jp))[0]
        if stem == "merged" or stem not in frames:
            continue
        rec = json.load(open(jp, encoding="utf-8"))
        if rec.get("names_done"):
            continue
        rgb, g = pixfirst.load(frames[stem])
        cols = rec["columns"]
        if len(cols) < 2:
            continue
        name_left, next_left = cols[0][0], cols[1][0]
        for r in rec["rows"]:
            if r["cut"] or not r["cells"]:
                continue
            ya, yb = r["y"]
            crop = rgb[max(0, ya - 6):yb + 6, max(0, name_left - 6):next_left - 10]
            reads = []
            for sc in (3.0, 2.0):
                got = pixfirst.ocr(crop, sc)
                reads.append("".join(w[4] for w in sorted(got, key=lambda w: w[0])).strip())
            reads.append(pixfirst.tess_word(crop))
            r["name_alt"] = reads
            pick = best(reads + [r["cells"][0]])
            r["cells"][0] = pick
        rec["names_done"] = True
        json.dump(rec, open(jp, "w", encoding="utf-8"), indent=1)
        n += 1
        print("%s names re-read (%d rows)" % (stem, sum(1 for r in rec["rows"] if r.get("name_alt"))), flush=True)
    print("NAMES DONE", n)
