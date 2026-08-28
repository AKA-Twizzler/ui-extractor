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
UI_WORDS = {"name", "date", "modified", "size", "kind", "datemodified", "today", "yesterday"}


def here(path):
    """The record's Windows path, as this side of the machine reaches it."""
    if os.name == "nt":
        return path
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


def rect_of(recs, ts, wi):
    for mm in recs:
        if mm.get("ts") == ts:
            for x in mm.get("windows") or []:
                if x["wi"] == wi:
                    return x["rect"]
    return [0, 0, 0, 0]


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
        # THE NAMES THE VIDEO ALREADY KNOWS THIS WINDOW BY: its own path bar's
        # crumbs, and the titles the reader confirmed on any window. A row of
        # the list is NOT among them - a row is what the folder holds, never
        # what it is called.
        known = []
        for p in m.get("panes") or []:
            for ln in p.get("lines") or []:
                if "below the list" in ln or "crumb" in ln:
                    for w in re.split(r"\s*\|\s*", re.sub(r"^\[[^\]]*\]\s*", "", ln)):
                        w = w.strip().rstrip(">\u203a ").strip()
                        if len(w) >= 3:
                            known.append(w)
        for mm in recs:
            for x in mm.get("windows") or []:
                if x.get("top") and x.get("top_from") != "reread":
                    for w in str(x["top"]).split(" | "):
                        if len(w) >= 3:
                            known.append(w.strip())
        known_keys = {re.sub(r"[^a-z0-9]", "", w.lower()): w for w in known}
        for w in m.get("windows") or []:
            if w.get("top"):
                continue
            cands = strips.get((m["ts"], w["wi"])) or []
            toks = [t for run in cands for t in run.split()]
            same_place = [runs2 for (ts2, wi2), runs2 in strips.items() if ts2 != m["ts"]
                          and same_rect(rect_of(recs, ts2, wi2), w["rect"])]
            other_keys = {re.sub(r"[^a-z0-9]", "", t2.lower())
                          for runs2 in same_place for run2 in runs2 for t2 in run2.split()}
            kept = []
            for t in toks:
                key = re.sub(r"[^a-z0-9]", "", t.lower())
                if len(key) < 3 or not re.search(r"[a-z]", key) or key in UI_WORDS:
                    continue
                # a solid word: letters enough, a vowel, not one letter
                # repeated - the icons beside a title come back as `eee`
                # and `Ss` on every strip alike, so repetition across
                # strips proves nothing about them
                solid = (len(key) >= 5 and re.search(r"[aeiouy]", key)
                         and len(set(re.sub(r"[^a-z]", "", key))) >= 3)
                if not solid:
                    continue
                elsewhere = key in other_keys
                inside = key in known_keys
                near = next((v for k2, v in known_keys.items()
                             if len(k2) >= 6 and len(k2) == len(key)
                             and sum(1 for a_, b_ in zip(k2, key) if a_ != b_) == 1), None)
                if near and near not in kept:
                    kept.append(near)             # one letter misread: the known spelling
                elif (elsewhere or inside) and t not in kept:
                    kept.append(known_keys.get(key, t))
            pick = None
            if kept:
                # a known name holding every kept word is the name itself
                # (`Company`, `Info`, `Product` -> `02 Company A (Info Product)`)
                keys_ = [re.sub(r"[^a-z0-9]", "", k.lower()) for k in kept]
                whole = [v for k2, v in known_keys.items() if all(k in k2 for k in keys_)]
                if whole:
                    pick = min(whole, key=len)
                else:
                    pick = " ".join(kept)
            if pick:
                w["top"] = pick
                w["top_from"] = "reread"
                filled += 1
                print(f"{m['ts']} window {w['wi']} {w['rect']}: {pick!r}   (strip read {toks})")
    if filled:
        if not os.path.exists(path + ".bak-titles"):
            shutil.copy2(path, path + ".bak-titles")     # the reader's own record, kept once
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(path + ".tmp", path)
    print(f"{filled} titles filled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
