"""Every frame of the memory window read pixels-first, then merged into one
card. Run under the Windows venv:
    python _probe/pixfirst_all.py <frames_dir_unc> <out_dir> [limit]
"""
import difflib, glob, json, os, re, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfirst

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def same_name(a, b):
    """Two readings of one name: equal once folded; one the other cut with
    dots; or close enough once folded that only the engine's wobble
    separates them (a letter dropped, an underscore read as a dot)."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    for cut, whole in ((a, b), (b, a)):
        if ".." in cut:
            head, tail = cut.split("..", 1)
            head, tail = norm(head.rstrip(".")), norm(tail.lstrip("."))
            w = norm(whole)
            if head and tail and w.startswith(head) and w.endswith(tail) and len(w) >= len(head) + len(tail):
                return True
    if min(len(na), len(nb)) >= 8 and difflib.SequenceMatcher(None, na, nb).ratio() >= 0.86:
        return True
    # a reading that lost its head (the pointer over it): the tail of the other
    short, long_ = (na, nb) if len(na) < len(nb) else (nb, na)
    return len(short) >= 0.6 * len(long_) and long_.endswith(short)

def merge(records):
    """The rows of every frame folded into one list: a full row (not cut,
    read with confidence) may open a group; a cut row may only join one.
    Each cell is the commonest full reading; the name the commonest whole
    one. The order is every frame's own sequence stitched in time order,
    anchored on the rows already placed."""
    groups = []
    def find(name):
        for gp in groups:
            if any(same_name(name, n) for n in gp["names"]):
                return gp
        return None
    # a frame of another folder (the two rows of the parent before the
    # memory folder opened) is not this window: fewer than five rows
    records = [rec for rec in records if len(rec["rows"]) >= 5]
    for pass_ in ("full", "cut"):
        for rec in records:
            for r in rec["rows"]:
                if not r["cells"] or not r["cells"][0].strip():
                    continue
                if (pass_ == "full") == bool(r["cut"]):
                    continue
                name = r["cells"][0].strip()
                hit = find(name)
                if hit is None:
                    if pass_ == "cut":
                        continue
                    hit = {"names": Counter(), "rows": []}; groups.append(hit)
                hit["names"][name] += 1
                hit["rows"].append(dict(r, frame=rec["frame"]))
    out = []
    for gp in groups:
        full = [r for r in gp["rows"] if not r["cut"]]
        pool = full or gp["rows"]
        whole = Counter(r["cells"][0] for r in pool if ".." not in r["cells"][0])
        name = (whole.most_common(1)[0][0] if whole else Counter(r["cells"][0] for r in pool).most_common(1)[0][0])
        cells = [name]
        ncol = max(len(r["cells"]) for r in pool)
        for k in range(1, ncol):
            c = Counter(r["cells"][k].strip() for r in pool if k < len(r["cells"]) and r["cells"][k].strip())
            cells.append(c.most_common(1)[0][0] if c else "")
        icon = Counter(r["icon"] for r in pool).most_common(1)[0][0]
        sel = any(r["selected"] for r in full)
        out.append({"name": name, "cells": cells, "icon": icon, "selected": sel, "seen": len(gp["rows"]), "full": len(full),
                    "names": dict(gp["names"])})
    def key_of(row):
        for i, g in enumerate(out):
            if same_name(row["cells"][0], g["name"]) or any(same_name(row["cells"][0], n) for n in g["names"]):
                return i
        return None
    order = []
    for rec in records:                       # time order
        seq = [key_of(r) for r in rec["rows"] if r["cells"] and r["cells"][0].strip()]
        seq = [k for k in seq if k is not None]
        prev = None
        for i, k in enumerate(seq):
            if k in order:
                prev = k; continue
            if prev is not None:
                order.insert(order.index(prev) + 1, k)
            else:
                later = next((j for j in seq[i + 1:] if j in order), None)
                if later is not None:
                    order.insert(order.index(later), k)
                else:
                    order.append(k)
            prev = k
    # A ROW SEEN IN ONE FRAME ONLY, standing between two rows every other
    # frame shows with a third between them, is that third row misread
    # (the pointer over it, a band across it): folded into it
    seqs = []
    for rec in records:
        seq = [key_of(r) for r in rec["rows"] if r["cells"] and r["cells"][0].strip()]
        seqs.append([k for k in seq if k is not None])
    folded = {}
    for i, g in enumerate(out):
        if g["seen"] != 1:
            continue
        for seq in seqs:
            if i not in seq:
                continue
            j = seq.index(i)
            prev_ = seq[j - 1] if j > 0 else None
            next_ = seq[j + 1] if j + 1 < len(seq) else None
            between = Counter()
            for s2 in seqs:
                if s2 is seq:
                    continue
                if prev_ is not None and next_ is not None:
                    for a in range(len(s2) - 2):
                        if s2[a] == prev_ and s2[a + 2] == next_:
                            between[s2[a + 1]] += 1
                elif next_ is not None:               # the stray heads its frame: the row before next_ elsewhere
                    for a in range(1, len(s2)):
                        if s2[a] == next_:
                            between[s2[a - 1]] += 1
                elif prev_ is not None:               # the stray ends its frame: the row after prev_ elsewhere
                    for a in range(len(s2) - 1):
                        if s2[a] == prev_:
                            between[s2[a + 1]] += 1
            if between:
                x, n = between.most_common(1)[0]
                if x != i and out[x]["seen"] >= 3:
                    folded[i] = x
            break
    for i, x in folded.items():
        out[x]["seen"] += 1
        out[x]["names"][out[i]["name"]] = out[x]["names"].get(out[i]["name"], 0) + 1
    order = [k for k in order if k not in folded]
    ordered = [out[k] for k in order] + [g for i, g in enumerate(out) if i not in order and i not in folded]
    return ordered

if __name__ == "__main__":
    fdir, out = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    frames = sorted(glob.glob(os.path.join(fdir, "*.png")))
    extra = [r"G:\Images\Move Memory Files Out of Claude Code Into Obsidian\Images\00-01-%s.png" % s for s in ("20", "30", "40")]
    frames = extra + frames
    if limit:
        frames = frames[:limit]
    recs = []
    for i, f in enumerate(frames):
        stem = os.path.splitext(os.path.basename(f))[0]
        jp = os.path.join(out, stem + ".json")
        if os.path.exists(jp):
            recs.append(json.load(open(jp, encoding="utf-8"))); continue
        try:
            rec = pixfirst.read_frame(f, out, "memory")
        except Exception as e:
            print("FAILED", stem, e); continue
        recs.append(rec)
        print("%d/%d %s rows=%d full=%d thumb=%s side=%s" % (i + 1, len(frames), stem, len(rec["rows"]), sum(1 for r in rec["rows"] if not r["cut"]), rec["thumb"], rec["side_thumb"]), flush=True)
    merged = merge(recs)
    json.dump(merged, open(os.path.join(out, "merged.json"), "w", encoding="utf-8"), indent=1)
    print("MERGED", len(merged), "rows")
    for g in merged:
        print(("SEL " if g["selected"] else "    ") + g["icon"].ljust(6), "%2d/%2d" % (g["full"], g["seen"]), " | ".join(g["cells"]))
    print("PIXFIRST DONE")
