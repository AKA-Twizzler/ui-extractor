#!/usr/bin/env python3
"""Write one video's whole story into one note.

    python chronicle.py <video> [pipeline args...]

Runs the chronological read -- every distinct screen, and every moment one
changed (pipeline.py --dense) -- and writes <Title>.md at the top of the
video's own folder. After the run the folder holds exactly three things:
the note, the scan, and Images/ with every picture the run extracted; any
image still lying at the top level is moved into Images/.

The record goes into the note inside one long fence, untouched: the
record's own indentation IS its layout, and Markdown re-rendering it as
code blocks and rules would scramble what the instruments wrote. A
four-backtick fence survives a terminal that happened to show three.
"""
import os
import shutil
import subprocess
import sys

import machine


def main():
    video = sys.argv[1]
    title = os.path.basename(os.path.dirname(video)) or "capture"
    out_dir = machine.here(f"/mnt/g/Images/{title}")
    r = subprocess.run(
        [sys.executable, "pipeline.py", video, "--dense"] + sys.argv[2:],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=os.path.dirname(os.path.abspath(__file__)))
    body = (r.stdout or "").rstrip("\n")
    if r.returncode != 0 or not body:
        sys.stderr.write(r.stderr or f"pipeline exited {r.returncode}\n")
        return r.returncode or 1
    note = os.path.join(out_dir, f"{title}.md")
    # the note is drawn from the run's records -- each window on the screen
    # as its own section, on the vault's style sheet -- and the run's own
    # output rides at the end as the moment-by-moment appendix. See draw.py;
    # a changed shape changes that file, never the readers
    import draw
    records = os.path.join(out_dir, "records.jsonl")
    if os.path.exists(records):
        text = draw.note(records, diary_text=body)
    else:
        text = (f"# {title}\n\n````text\n" + body + "\n````\n")
    tmp = note + ".tmp-write"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, note)
    imgs = os.path.join(out_dir, "Images")
    os.makedirs(imgs, exist_ok=True)
    for name in os.listdir(out_dir):
        src = os.path.join(out_dir, name)
        if name.lower().endswith((".png", ".jpg")):
            shutil.move(src, os.path.join(imgs, name))
        elif name in ("_looks", "_zones") and os.path.isdir(src):
            # working frames from before the Images/ layout
            dst = os.path.join(imgs, name)
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(src):
                if not os.path.exists(os.path.join(dst, f)):
                    shutil.move(os.path.join(src, f), os.path.join(dst, f))
            if not os.listdir(src):
                os.rmdir(src)
    print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
