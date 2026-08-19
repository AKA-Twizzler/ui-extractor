#!/usr/bin/env python3
"""The acceptance pass: one chronological note for every video.

    python acceptance.py [--redo]

Walks the library smallest-first so notes start appearing early, and runs
chronicle.py per video. Resumable by construction: a video whose note
already exists is skipped (unless --redo), so a machine restart mid-pass
costs only the video it interrupted.
"""
import glob
import os
import subprocess
import sys

import machine


def main():
    videos = []
    for folder in sorted(glob.glob(machine.here("/mnt/g/Video/*"))):
        found = sorted(glob.glob(os.path.join(folder, "*.mp4")))
        if found:
            videos.append((os.path.getsize(found[0]), found[0]))
    videos.sort()
    print(f"{len(videos)} videos in the library", flush=True)
    done = failed = skipped = 0
    for _, video in videos:
        title = os.path.basename(os.path.dirname(video))
        note = machine.here(f"/mnt/g/Images/{title}/{title}.md")
        if os.path.exists(note) and "--redo" not in sys.argv:
            skipped += 1
            print(f"  have  {title}", flush=True)
            continue
        print(f"  read  {title} ...", flush=True)
        r = subprocess.run(
            [sys.executable, "chronicle.py", video],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace",
            cwd=os.path.dirname(os.path.abspath(__file__)))
        if r.returncode == 0:
            done += 1
            print(f"  ok    {title}", flush=True)
        else:
            failed += 1
            tail = (r.stderr or r.stdout or "").strip().splitlines()
            print(f"  FELL  {title}: {tail[-1][:160] if tail else '?'}",
                  flush=True)
    print(f"\n{done} written, {skipped} already there, {failed} fell over",
          flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
