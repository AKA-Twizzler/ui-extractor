#!/usr/bin/env python3
"""Run the pipeline over the whole library and say what looks wrong.

    python3 sweep.py                    every video, four moments each
    python3 sweep.py --at 6             six moments each
    python3 sweep.py --only obsidian    only videos whose folder matches

Why this exists: `checks.py` proves the stages against frames whose answer is
known, which is what keeps a fixed answer fixed. It cannot tell us whether the
NEXT video holds a shape no reader has met. Only running it can, and reading
every line of that by eye does not scale past a few videos.

So the run is done for real -- one `pipeline.py` per video, the same program
and the same path a full pass would take -- and the output is then read for
the marks that a fault leaves behind. Nothing here decides that something is
wrong. It ranks what to look at, and the looking is still done by a person.

The smells, each one learned from a fault that had already happened:

  fell over      a reader raised. Always a fault, and the run steps over it.
  data heading   a table headed by a date, a size or a bare number is a table
                 that lost its heading row
  odd script     Chinese or Cyrillic letters in an English interface are the
                 recogniser guessing at shapes, not reading words
  all unsettled  a terminal or tree where most lines are marked is a reader
                 that took something which is not one
  empty frame    a frame with an interface on it that produced no reading at
                 all -- the silent loss this build keeps finding
  bare fences    a document that is only a properties block, which is the
                 shape the invented-frontmatter fault always took
"""
import glob
import os
import re
import subprocess
import sys

import machine

VIDEO_ROOT = machine.here("/mnt/g/Video")
OUT = machine.here("/mnt/g/Images/_sweep")

DATA_HEADING = re.compile(
    r"^\s*\|?\s*(\d{1,2}[/.]\d|\d+\s?(KB|MB|GB|bytes)\b|"
    r"\w{3}\s?\d{1,2},?\s?20\d\d|\d+$)", re.I)
ODD_SCRIPT = re.compile(r"[Ѐ-ӿ一-鿿぀-ヿ]")


def moments(seconds, how_many):
    """Spread the moments through the video, away from its very ends."""
    step = seconds / (how_many + 1)
    return [f"{int(t)//3600:02d}:{int(t)%3600//60:02d}:{int(t)%60:02d}"
            for t in (step * (i + 1) for i in range(how_many))]


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def smells(text):
    """What in this output is worth a person's eyes, and why."""
    found = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "fell over" in line:
            found.append(("fell over", line.strip()[:150]))
        if ODD_SCRIPT.search(line):
            found.append(("odd script", line.strip()[:110]))
    # a table's heading row is the line after the columns label -- which may
    # carry a place suffix now, so the match is the phrase, not the bracket
    for i, line in enumerate(lines):
        if "a list of columns" not in line and "[block" not in line:
            continue
        for head in lines[i + 1:i + 3]:
            if head.lstrip().startswith("|") and DATA_HEADING.search(
                    head.split("|")[1] if head.count("|") > 1 else ""):
                found.append(("data heading", head.strip()[:110]))
                break
    # a reader that took something which is not what it reads
    # panes may sit nested under a window header now, so a block opens on the
    # label wherever it is indented, and closes on the next label, window
    # header, or moment line
    block, marked, total = None, 0, 0
    for line in lines + ["  ---end---"]:
        s = line.lstrip()
        if s.startswith(("[pane", "[window")) or line.startswith("---"):
            if block and total >= 4 and marked * 2 > total:
                found.append(("all unsettled",
                              f"{block}: {marked} of {total} lines marked"))
            block = s[:60] if s.startswith("[pane") else None
            marked = total = 0
        elif block and line.strip():
            total += 1
            if "other engine read" in line or "only one engine" in line:
                marked += 1
    # a frame that carried an interface and said nothing about it
    for i, line in enumerate(lines):
        m = re.search(r"interface on (\d+)% of the frame", line)
        if not m or int(m.group(1)) < 40:
            continue
        rest = []
        for nxt in lines[i + 1:]:
            if nxt.startswith("--- "):
                break
            rest.append(nxt)
        if not any("[pane" in r for r in rest):
            found.append(("empty frame", line.strip()[:110]))
    # a document that is nothing but a properties block
    for i, line in enumerate(lines):
        if "an open document" not in line or "[pane" not in line:
            continue
        body = []
        for nxt in lines[i + 1:]:
            s = nxt.lstrip()
            if (not s or nxt.startswith("--- ")
                    or s.startswith(("[pane", "[window", "[a panel", "[drawn"))):
                break
            body.append(nxt.strip())
        if body and body.count("---") >= 2 and len(body) <= 6:
            found.append(("bare fences", " / ".join(body)[:110]))
    return found


def main():
    how_many = int(sys.argv[sys.argv.index("--at") + 1]) if "--at" in sys.argv else 4
    only = sys.argv[sys.argv.index("--only") + 1].lower() if "--only" in sys.argv else None
    os.makedirs(OUT, exist_ok=True)

    folders = sorted(d for d in os.listdir(VIDEO_ROOT)
                     if os.path.isdir(os.path.join(VIDEO_ROOT, d)))
    if only:
        folders = [d for d in folders if only in d.lower()]

    tally = {}
    for d in folders:
        found = sorted(glob.glob(os.path.join(VIDEO_ROOT, d, "*.mp4")))
        if not found:
            print(f"  --  {d}: no video")
            continue
        video = found[0]
        secs = duration(video)
        if secs < 60:
            print(f"  --  {d}: {secs:.0f}s, too short")
            continue
        report = os.path.join(OUT, re.sub(r"[^\w -]", "_", d) + ".txt")
        if not os.path.exists(report):
            at = ",".join(moments(secs, how_many))
            r = subprocess.run([sys.executable, "pipeline.py", video, "--at", at],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            with open(report, "w", encoding="utf-8") as fh:
                fh.write(r.stdout or "")
                if r.returncode:
                    fh.write(f"\n[PIPELINE EXITED {r.returncode}]\n{r.stderr}")
        text = open(report, encoding="utf-8").read()
        bad = smells(text)
        if "[PIPELINE EXITED" in text:
            bad.append(("run died", text.split("[PIPELINE EXITED", 1)[1][:200]))
        for kind, _ in bad:
            tally[kind] = tally.get(kind, 0) + 1
        mark = "ok  " if not bad else f"{len(bad):<4}"
        print(f"  {mark}{d}")
        for kind, detail in bad[:8]:
            print(f"        {kind:<14} {detail}")
        if len(bad) > 8:
            print(f"        ... and {len(bad) - 8} more")

    print(f"\n{sum(tally.values())} things to look at across {len(folders)} "
          f"videos: {tally or 'none'}")
    print(f"reports in {OUT}")


if __name__ == "__main__":
    main()
