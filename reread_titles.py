#!/usr/bin/env python3
"""A window's title read again off the frame, where the reader's two-engine
strip confirmed nothing.

    python3 reread_titles.py <records.jsonl>

Every measured window has its top strip saved beside the frames
(`HH-MM-SS_top_<x>_<y>_<h>.png`, the strip at three times size). The
pipeline's `top_text` asks both engines to agree on it and, when they do
not, writes no title - so the window at 00:03:30 of the memory-files video
stood titled `Assets` on the screen and nameless in the record, and the
drawing named it after the crumb before it.

This reads the taller strip again with tesseract alone and keeps a word
only on evidence the first pass did not have: the same word read on the
strip of ANOTHER moment where the window stood at the same place (two
frames agreeing is the confirmation), or the word standing in the window's
own path bar or list. Nothing is written that no frame said. The record is
rewritten in place with a `.bak-titles` copy beside it, and each title
filled carries `top_from: "reread"` so it can be told from the reader's.
"""
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import machine

JUNK = re.compile(r"^[^A-Za-z0-9]*$")


def here(path):
    if len(path) > 2 and path[1] == ":":
        return "/mnt/" + path[0].lower() + path[2:].replace("\\", "/")
    return path


def read_strip(png):
    exe = machine.tesseract_or_refuse()
    r = subprocess.run([exe, png, "stdout", "-l", "eng", "--psm", "7"],
                       capture_output=True, timeout=120)
    text = r.stdout.decode("utf-8", "replace")
    toks = [t for t in re.split(r"\s+", text) if t and not JUNK.match(t)]
    # the title is a run of real words; icons come back as scraps
    words = []
    for t in toks:
        t2 = t.strip("|.,;:'\"«»“”‘’()[]{}")
        if len(t2) >= 2 and re.search(r"[A-Za-z]{2}", t2) and not re.fullmatch(r"[0O]+", t2):
            words.append(t2)
    return words


def runs(words):
    """Maximal runs of word-like tokens, longest first."""
    out, cur = [], []
    for w in words:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._'()&-]*", w) and not re.fullmatch(r"[A-Za-z]", w):
            cur.append(w)
        else:
            if cur:
                out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return sorted(out, key=len, reverse=True)


def same_rect(a, b, slack=40):
    return all(abs(x - y) <= slack for x, y in zip(a, b))


def main():
    path = sys.argv[1]
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    imgs = None
    strips = {}          # (ts, wi) -> candidate runs
    for m in recs:
        if m.get("kind") != "moment":
            continue
        frame = here(m["frame"])
        imgs = os.path.dirname(frame)
        tag = m["ts"].replace(":", "-")
        for w in m.get("windows") or []:
            a, t, c, d = w["rect"]
            H = m["size"][1]
            cands = []
            for share in (0.052, 0.026):
                sh = max(24, round(H * share))
                png = os.path.join(imgs, f"{tag}_top_{a}_{t}_{sh}.png")
                if not os.path.exists(png):
                    continue
                cands.extend(runs(read_strip(png)))
            strips[(m["ts"], w["wi"])] = cands
    filled = 0
    for m in recs:
        if m.get("kind") != "moment":
            continue
        own = set()
        for p in m.get("panes") or []:
            for ln in p.get("lines") or []:
                for w in re.split(r"\s*\|\s*", re.sub(r"^\[[^\]]*\]\s*", "", ln)):
                    own.add(re.sub(r"[^a-z0-9]", "", w.lower()))
        for w in m.get("windows") or []:
            if w.get("top"):
                continue
            cands = strips.get((m["ts"], w["wi"])) or []
            pick = None
            for run in cands:
                key = re.sub(r"[^a-z0-9]", "", run.lower())
                if len(key) < 3:
                    continue
                # confirmation one: the same run on another moment's strip of
                # a window standing at the same place
                elsewhere = any(re.sub(r"[^a-z0-9]", "", r2.lower()) == key
                                for (ts2, wi2), runs2 in strips.items()
                                if ts2 != m["ts"] for r2 in runs2
                                if same_rect(next(x["rect"] for x in next(mm for mm in recs if mm.get("ts") == ts2)["windows"] if x["wi"] == wi2), w["rect"]))
                # confirmation two: the run stands in the window's own bar or list
                inside = key in own or any(len(key) >= 5 and (key in o or o in key) for o in own if len(o) >= 5)
                if elsewhere or inside:
                    pick = run
                    break
            if pick:
                w["top"] = pick
                w["top_from"] = "reread"
                filled += 1
                print(f"{m['ts']} window {w['wi']} {w['rect']}: {pick!r}")
    if filled:
        shutil.copy2(path, path + ".bak-titles")
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(path + ".tmp", path)
    print(f"{filled} titles filled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
